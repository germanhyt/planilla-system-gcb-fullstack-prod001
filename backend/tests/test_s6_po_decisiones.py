"""Decisiones del PO (pt54u): HE programadas GCB SA al banco; empresa del usuario editable solo por admin."""
from datetime import date

import pytest
from sqlalchemy import select

from app.engine import calcular_asistencia_dia, recalcular_trabajador_periodo
from app.models import Asistencia, Auditoria, BancoHorasCompensatorias, HEProgramada, RuleSet, Usuario
from app.rules import BASE, CAVAS, GCB_SA_V2, efectivas
from tests.test_engine_golden_gcbsa import LUNES, REGLAS, lima
from tests.test_engine_golden_gcbsa import gcb as gcb  # noqa: F401 - fixture reutilizada


def test_destino_programadas_por_empresa():
    assert BASE["horas_extra"]["destino_programadas"] == "pago"
    assert efectivas(CAVAS)["horas_extra"]["destino_programadas"] == "pago"
    assert REGLAS["horas_extra"]["destino_programadas"] == "pago"  # GCB SA v1 (restaurada, pt57u)
    assert V2["horas_extra"]["destino_programadas"] == "compensacion"  # GCB SA v2


V2 = efectivas(GCB_SA_V2)


def con_v2(db, emp):
    """La empresa de prueba pasa a GCB SA v2 (nueva version de rule_set, como en prod desde 2026-11-01)."""
    db.add(RuleSet(empresa_id=emp.id, version=2, valid_from=date(2025, 1, 1), config=GCB_SA_V2, motivo="test v2"))
    db.commit()


def _he(db, t, horas=2.0):
    creador = db.query(Usuario).first().id
    db.add(HEProgramada(trabajador_id=t.id, dia=LUNES, horas=horas, creado_por=creador))
    db.commit()


def test_he_programada_gcb_va_al_banco_no_a_pago(db, gcb):  # noqa: F811
    _, trabajador, marcar = gcb
    t = trabajador("dia")
    _he(db, t)
    marcar(t, lima(LUNES, 8), lima(LUNES, 18))
    r = calcular_asistencia_dia(db, t.id, LUNES, V2)
    assert (r["horas_extra_25"], r["horas_extra_35"], r["horas_extra_banco"], r["exceso_no_programado"]) == (0, 0, 2.0, 0)
    pago = calcular_asistencia_dia(db, t.id, LUNES, efectivas(CAVAS) | {"dia_operativo": REGLAS["dia_operativo"]})
    assert (pago["horas_extra_25"], pago["horas_extra_banco"]) == (2.0, 0.0)


def test_cierre_acredita_banco_una_sola_vez(client, H, db, gcb):  # noqa: F811
    emp, trabajador, marcar = gcb
    con_v2(db, emp)
    t = trabajador("dia")
    _he(db, t)
    marcar(t, lima(LUNES, 8), lima(LUNES, 18))
    assert recalcular_trabajador_periodo(db, t.id, "2025-03")
    per = {"empresa_id": emp.id, "periodo": "2025-03"}
    c = client.post("/periodos/cerrar", headers=H["admin"], json=per | {"confirmar": True})
    assert c.status_code in (200, 201), c.text
    # re-cierre tras reapertura: no duplica el credito
    assert client.post(f"/periodos/reabrir/{c.json()['id']}", headers=H["admin"],
                       json={"razon_reapertura": "prueba de idempotencia"}).status_code == 200
    assert client.post("/periodos/cerrar", headers=H["admin"], json=per | {"confirmar": True}).status_code in (200, 201)
    db.expire_all()
    movs = db.scalars(select(BancoHorasCompensatorias).where(BancoHorasCompensatorias.trabajador_id == t.id)).all()
    assert [(float(m.horas), m.tipo) for m in movs] == [(2.0, "credito")]
    a = db.scalar(select(Asistencia).where(Asistencia.trabajador_id == t.id))
    assert float(a.horas_extra_25) == 0 and float(a.horas_extra_banco) == 2.0
    e = client.post("/reportes/export-planilla-core", headers=H["admin"], params=per | {"formato": "json"}).json()
    assert not [li for li in e["lineas"] if li["trabajador_codigo"] == t.codigo and li["concepto_codigo"] in ("HE25", "HE35")]


@pytest.fixture
def jefe_ref(db):
    return db.scalar(select(Usuario).where(Usuario.email == "jefe.refugio@demo.gcb.pe"))


def test_admin_cambia_empresa_auditado(client, H, db, ids):
    u = db.scalar(select(Usuario).where(Usuario.email == "rrhh.gcb@demo.gcb.pe"))
    try:
        r = client.put(f"/usuarios/{u.id}/empresa", headers=H["admin"], json={"empresa_id": ids["emp"]["CAVAS"]})
        assert r.status_code == 200 and r.json()["empresa_id"] == ids["emp"]["CAVAS"]
        assert db.scalar(select(Auditoria).where(Auditoria.accion == "cambiar_empresa", Auditoria.entidad_id == str(u.id)))
        assert client.put(f"/usuarios/{u.id}/empresa", headers=H["admin"], json={"empresa_id": None}).json()["empresa_id"] is None
    finally:
        client.put(f"/usuarios/{u.id}/empresa", headers=H["admin"], json={"empresa_id": ids["emp"]["GCBSA"]})


def test_solo_admin_y_jefe_consistente(client, H, ids, jefe_ref):
    assert client.put(f"/usuarios/{jefe_ref.id}/empresa", headers=H["rrhh"], json={"empresa_id": None}).status_code == 403
    r = client.put(f"/usuarios/{jefe_ref.id}/empresa", headers=H["admin"], json={"empresa_id": ids["emp"]["CAVAS"]})
    assert r.status_code == 422
    assert client.put("/usuarios/999999/empresa", headers=H["admin"], json={"empresa_id": None}).status_code == 404
