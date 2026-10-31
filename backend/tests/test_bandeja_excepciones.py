"""Sprint 3 / Incremento 2: bandeja de excepciones (permisos, filtros, acciones con destino HE) y bolsa de horas."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models import Asistencia, BancoHorasCompensatorias, RegularizacionHE, RuleSet, Trabajador

DESDE, HASTA = "2025-03-01", "2025-03-31"


def _trab(db, codigo):
    return db.scalar(select(Trabajador).where(Trabajador.codigo == codigo))


def _he(db, codigo, dia, exceso, trabajadas=None):
    t = _trab(db, codigo)
    rs = db.scalar(select(RuleSet.id).where(RuleSet.empresa_id == t.empresa_id).limit(1))
    a = Asistencia(trabajador_id=t.id, dia_operativo=dia, periodo=dia.strftime("%Y-%m"), horas_programadas=8,
                   horas_trabajadas=trabajadas if trabajadas is not None else 8 + exceso, tardanza_min=0, horas_extra_25=0,
                   horas_extra_35=0, horas_nocturnas=0, exceso_no_programado=exceso, rule_set_id=rs)
    db.add(a)
    db.flush()
    r = RegularizacionHE(asistencia_id=a.id, trabajador_id=t.id, horas_exceso=exceso, estado="pendiente")
    db.add(r)
    db.commit()
    return r.id, a.id


@pytest.fixture(scope="module")
def casos(H):
    from app.db import SessionLocal
    with SessionLocal() as db:
        c = {"cav": _he(db, "CAV-003", date(2025, 3, 3), 2.5), "par": _he(db, "PAR-003", date(2025, 3, 4), 3.0),
             "rech": _he(db, "CAV-004", date(2025, 3, 5), 1.0), "mixto": _he(db, "CAV-005", date(2025, 3, 6), 3.0),
             "par_pago": _he(db, "PAR-004", date(2025, 3, 7), 1.0)}
        # PT85 con 6 h/día en la semana del 10/03 -> alerta PT (no bloquea)
        for i in range(5):
            c[f"pt{i}"] = _he(db, "CAV-008", date(2025, 3, 10) + timedelta(days=i), 0.5 if i == 0 else 0.25, trabajadas=6)
    return c


def _bandeja(client, h, **params):
    q = "&".join(f"{k}={v}" for k, v in {"desde": DESDE, "hasta": HASTA, **params}.items())
    r = client.get(f"/excepciones/bandeja?{q}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_trabajador_no_ve_bandeja(client, H):
    assert client.get(f"/excepciones/bandeja?desde={DESDE}&hasta={HASTA}", headers=H["trabajador"]).status_code == 403


def test_jefe_ve_solo_su_unidad_rrhh_todo(client, H, casos):
    jefe = {i["ref_id"] for i in _bandeja(client, H["jefe"], tipo="he_no_programada")}
    assert casos["cav"][0] in jefe and casos["par"][0] not in jefe
    parking = {i["ref_id"] for i in _bandeja(client, H["jefe_parking"], tipo="he_no_programada")}
    assert casos["par"][0] in parking and casos["cav"][0] not in parking
    for rol in ("rrhh", "admin"):
        todos = {i["ref_id"] for i in _bandeja(client, H[rol], tipo="he_no_programada")}
        assert {casos["cav"][0], casos["par"][0]} <= todos


def test_destino_default_por_empresa(client, H, casos):
    items = {i["ref_id"]: i for i in _bandeja(client, H["rrhh"], tipo="he_no_programada")}
    assert items[casos["cav"][0]]["destino_default"] == "pago" and items[casos["cav"][0]]["empresa"] == "CAVAS"
    assert items[casos["par"][0]]["destino_default"] == "compensacion"
    assert items[casos["cav"][0]]["accionable"] is True


def test_jefe_no_decide_otra_unidad(client, H, casos):
    r = client.post(f"/regularizaciones/{casos['par'][0]}/decidir", json={"aprobar": True}, headers=H["jefe"])
    assert r.status_code == 403
    assert client.post(f"/regularizaciones/{casos['par'][0]}/decidir", json={"aprobar": True},
                       headers=H["trabajador"]).status_code == 403


def test_regularizar_sin_destino_usa_default_pago_cavas(client, H, casos, db):
    r = client.post(f"/regularizaciones/{casos['cav'][0]}/decidir", json={"aprobar": True}, headers=H["jefe"])
    assert r.status_code == 200, r.text
    assert r.json()["destino"] == "pago"
    a = db.get(Asistencia, casos["cav"][1])
    assert float(a.horas_extra_25) == 2.0 and float(a.horas_extra_35) == 0.5 and float(a.exceso_no_programado) == 0
    # ya procesada
    assert client.post(f"/regularizaciones/{casos['cav'][0]}/decidir", json={"aprobar": True},
                       headers=H["jefe"]).status_code == 400


def test_regularizar_default_compensacion_gcb_y_saldo(client, H, casos, db):
    t = _trab(db, "PAR-003")
    antes = client.get("/banco-horas/saldos", headers=H["rrhh"]).json()
    s0 = next(x["saldo_horas"] for x in antes if x["id"] == t.id)
    r = client.post(f"/regularizaciones/{casos['par'][0]}/decidir", json={"aprobar": True}, headers=H["jefe_parking"])
    assert r.status_code == 200 and r.json()["destino"] == "compensacion"
    despues = client.get("/banco-horas/saldos", headers=H["jefe_parking"]).json()
    assert next(x["saldo_horas"] for x in despues if x["id"] == t.id) == s0 + 3.0


def test_destino_explicito_pago_en_gcb(client, H, casos, db):
    r = client.post(f"/regularizaciones/{casos['par_pago'][0]}/decidir", json={"aprobar": True, "destino": "pago"},
                    headers=H["rrhh"])
    assert r.status_code == 200 and r.json()["destino"] == "pago"
    assert float(db.get(Asistencia, casos["par_pago"][1]).horas_extra_25) == 1.0


def test_mixto_con_horas_pago(client, H, casos, db):
    rid = casos["mixto"][0]
    bad = client.post(f"/regularizaciones/{rid}/decidir", json={"aprobar": True, "destino": "mixto", "horas_pago": 5},
                      headers=H["jefe"])
    assert bad.status_code == 400
    r = client.post(f"/regularizaciones/{rid}/decidir", json={"aprobar": True, "destino": "mixto", "horas_pago": 1},
                    headers=H["jefe"])
    assert r.status_code == 200
    assert float(db.get(Asistencia, casos["mixto"][1]).horas_extra_25) == 1.0
    mov = db.scalar(select(BancoHorasCompensatorias).where(BancoHorasCompensatorias.regularizacion_id == rid))
    assert float(mov.horas) == 2.0


def test_rechazar_y_filtro_estado(client, H, casos):
    rid = casos["rech"][0]
    r = client.post(f"/regularizaciones/{rid}/decidir", json={"aprobar": False, "observacion": "No solicitado"},
                    headers=H["jefe"])
    assert r.status_code == 200 and r.json()["estado"] == "rechazado"
    rech = _bandeja(client, H["jefe"], estado="rechazado")
    assert any(i["ref_id"] == rid and not i["accionable"] for i in rech)
    assert all(i["estado"] == "pendiente" for i in _bandeja(client, H["jefe"], estado="pendiente"))


def test_alerta_pt_no_bloquea(client, H, casos):
    alertas = [i for i in _bandeja(client, H["jefe"], tipo="pt_alerta") if i["trabajador"]["codigo"] == "CAV-008"]
    assert alertas and alertas[0]["dia"] == "2025-03-10" and "PT85" in alertas[0]["detalle"]
    he = {i["ref_id"]: i for i in _bandeja(client, H["jefe"], tipo="he_no_programada")}
    assert he[casos["pt0"][0]]["alerta_pt"]
    r = client.post(f"/regularizaciones/{casos['pt0'][0]}/decidir", json={"aprobar": True}, headers=H["jefe"])
    assert r.status_code == 200  # la alerta es informativa
    # RRHH ve la alerta; jefe de parking no
    assert not [i for i in _bandeja(client, H["jefe_parking"], tipo="pt_alerta") if i["trabajador"]["codigo"] == "CAV-008"]


def test_filtro_tipo_y_rango_invalido(client, H, casos):
    assert all(i["tipo"] == "pt_alerta" for i in _bandeja(client, H["rrhh"], tipo="pt_alerta"))
    assert client.get("/excepciones/bandeja?desde=2025-03-10&hasta=2025-03-01", headers=H["rrhh"]).status_code == 400
    assert client.get(f"/excepciones/bandeja?desde={DESDE}&hasta={HASTA}&tipo=otro", headers=H["rrhh"]).status_code == 422


def test_bolsa_trabajador_solo_lo_suyo(client, H, db):
    mios = client.get("/banco-horas/saldos", headers=H["trabajador"]).json()
    assert [x["codigo"] for x in mios] == ["CAV-007"]
    otro = _trab(db, "CAV-001")
    assert client.get(f"/banco-horas/historial/{otro.id}", headers=H["trabajador"]).status_code == 403
    assert client.get(f"/banco-horas/historial/{mios[0]['id']}", headers=H["trabajador"]).status_code == 200


def test_bolsa_jefe_su_unidad_rrhh_todo(client, H):
    jefe = client.get("/banco-horas/saldos", headers=H["jefe"]).json()
    assert jefe and all(x["codigo"].startswith("CAV-") for x in jefe)
    todos = {x["codigo"][:3] for x in client.get("/banco-horas/saldos", headers=H["rrhh"]).json()}
    assert {"CAV", "PAR"} <= todos
    con = client.get("/banco-horas/saldos?solo_con_movimientos=true", headers=H["admin"]).json()
    assert all(x["movimientos"] > 0 for x in con)


def test_seed_ejemplos_idempotente(client, H):
    import seed
    seed.main()
    seed.main()
    from app.db import SessionLocal
    with SessionLocal() as db:
        n = db.scalar(select(BancoHorasCompensatorias.id).where(BancoHorasCompensatorias.origen.like("Seed:%")).limit(1))
        cnt = len(db.scalars(select(BancoHorasCompensatorias.id).where(
            BancoHorasCompensatorias.origen.like("Seed:%"))).all())
    assert n and cnt == 3
    mio = client.get("/banco-horas/saldos", headers=H["trabajador"]).json()[0]
    assert mio["saldo_horas"] == 2.0
