"""Sprint 7: hardening de la integracion con Planilla Core.

(a) export PC-ASIS-1.2 versionado (checksum, idempotente, historial, contrato, banco de horas, lote por empresa)
(b) trabajos RQ con progreso (umbral sync, fallback sin Redis)
(c) alertas internas RRHH
(d) seed Parking + etiqueta de ventana nocturna desde configuracion
"""
import hashlib
import json
import os
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app import trabajos
from app.config import settings
from app.models import (
    Asistencia,
    BancoHorasCompensatorias,
    BonoNocturno,
    Empresa,
    ExportPlanilla,
    HorarioPlan,
    Notificacion,
    RegularizacionHE,
    RuleSet,
    Trabajador,
)

PER = "2027-02"


def _emp(db, codigo):
    return db.query(Empresa).filter(Empresa.codigo == codigo).one()


def _otra(db):
    return db.query(Empresa).filter(Empresa.codigo != "CAVAS").order_by(Empresa.id).first()


def _t(db, empresa_id, n=0):
    return db.query(Trabajador).filter(Trabajador.empresa_id == empresa_id).order_by(Trabajador.codigo.desc())[n]


def _rs(db, empresa_id):
    return db.query(RuleSet).filter(RuleSet.empresa_id == empresa_id).order_by(RuleSet.valid_from).first().id


@pytest.fixture(scope="module")
def esc():
    """CAVAS 2027-02: un trabajador con horas, HE y movimientos de banco de horas."""
    from app.db import SessionLocal
    db = SessionLocal()
    cav = _emp(db, "CAVAS")
    t = _t(db, cav.id, 2)
    rs = _rs(db, cav.id)
    for i in range(2):
        db.add(Asistencia(trabajador_id=t.id, dia_operativo=date(2027, 2, 1) + timedelta(days=i), periodo=PER,
                          horas_programadas=8, horas_trabajadas=9, horas_extra_25=1, horas_nocturnas=1, rule_set_id=rs))
    db.add(BancoHorasCompensatorias(trabajador_id=t.id, fecha_movimiento=date(2027, 2, 3), tipo="credito", horas=3,
                                    saldo_anterior=0, saldo_nuevo=3, origen="test s7"))
    db.add(BancoHorasCompensatorias(trabajador_id=t.id, fecha_movimiento=date(2027, 2, 4), tipo="debito", horas=1,
                                    saldo_anterior=3, saldo_nuevo=2, origen="test s7"))
    db.commit()
    out = {"emp": cav.id, "tid": t.id, "codigo": t.codigo, "otra": _otra(db).id}
    db.close()
    return out


def _exp(client, H, emp, formato="json", rol="rrhh", **kw):
    return client.post("/reportes/export-planilla-core", headers=H[rol],
                       params={"periodo": PER, "empresa_id": emp, "formato": formato} | kw)


# ---------------------------------------------------------------- (a) export
def test_export_checksum_e_idempotencia(client, H, esc):
    r1 = _exp(client, H, esc["emp"])
    assert r1.status_code == 200, r1.text
    j = r1.json()
    assert j["layout_version"] == "PC-ASIS-1.2" and j["estado"] == "PRELIMINAR"
    assert r1.headers["x-export-checksum"] == j["checksum"] and len(j["checksum"]) == 64
    assert r1.headers["x-export-reutilizada"] == "0"
    # checksum = sha256 del JSON canonico de negocio (sin version ni fecha)
    canon = {k: j[k] for k in ("layout_version", "empresa_codigo", "empresa_ruc", "periodo", "estado")}
    canon["lineas"] = j["lineas"]
    assert hashlib.sha256(json.dumps(canon, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                          .encode()).hexdigest() == j["checksum"]
    r2 = _exp(client, H, esc["emp"])
    assert r2.headers["x-export-reutilizada"] == "1" and r2.content == r1.content  # misma version, mismos bytes
    assert r2.headers["x-export-version"] == r1.headers["x-export-version"]


def test_export_nueva_version_si_cambia_y_historial(client, H, esc, db):
    v1 = _exp(client, H, esc["emp"]).json()
    adm = db.execute(__import__("sqlalchemy").text("select id from usuario where email='admin@demo.gcb.pe'")).scalar()
    db.add(BonoNocturno(trabajador_id=esc["tid"], periodo=PER, cantidad=1, monto=20, estado="aprobado",
                        registrado_por=adm))
    db.commit()
    r = _exp(client, H, esc["emp"])
    v2 = r.json()
    assert v2["version_archivo"] == v1["version_archivo"] + 1 and v2["checksum"] != v1["checksum"]
    assert any(li["concepto_codigo"] == "B3AM" and li["monto"] == 20 for li in v2["lineas"])
    hist = client.get("/reportes/export-planilla-core/versiones", headers=H["rrhh"],
                      params={"empresa_id": esc["emp"], "periodo": PER}).json()
    js = [h for h in hist if h["formato"] == "json"]
    assert [h["version"] for h in js][:2] == [v2["version_archivo"], v1["version_archivo"]]
    assert "contenido" not in js[0]
    old = client.get(f"/reportes/export-planilla-core/versiones/{js[1]['id']}", headers=H["rrhh"])
    assert old.status_code == 200 and old.json()["checksum"] == v1["checksum"]
    assert old.headers["x-export-checksum"] == v1["checksum"]


def test_export_csv_banco_de_horas_y_conceptos(client, H, esc):
    r = _exp(client, H, esc["emp"], formato="csv")
    filas = [x.split(";") for x in r.text.strip().split("\n")]
    cab = filas[0]
    mias = [dict(zip(cab, f)) for f in filas[1:] if f[cab.index("trabajador_codigo")] == esc["codigo"]]
    by = {m["concepto_codigo"]: m for m in mias}
    assert float(by["BHCRE"]["cantidad"]) == 3 and float(by["BHDEB"]["cantidad"]) == 1
    assert float(by["BHSAL"]["cantidad"]) == 2 and all(m["layout_version"] == "PC-ASIS-1.2" for m in mias)
    j = _exp(client, H, esc["emp"]).json()
    assert {"BHCRE", "BHDEB", "BHSAL"} <= set(j["conceptos"])
    assert j["conceptos"]["HNOC"]["descripcion"] == "Horas nocturnas 22:00-06:00"


def test_export_valida_contrato(client, H, esc):
    from app.export_pc import ExportPC
    j = _exp(client, H, esc["emp"]).json()
    ExportPC.model_validate(j)
    with pytest.raises(ValidationError):
        ExportPC.model_validate(j | {"lineas": [j["lineas"][0] | {"concepto_codigo": "XX"}]})
    with pytest.raises(ValidationError):
        ExportPC.model_validate(j | {"extra": 1})


def test_export_contrato_invalido_no_persiste(db, esc, monkeypatch):
    from app import export_pc
    from app.routers import reportes
    monkeypatch.setattr(reportes, "_lineas", lambda regs: [{"trabajador_codigo": "", "concepto_codigo": "ZZ"}])
    antes = db.query(ExportPlanilla).count()
    with pytest.raises(ValidationError):
        export_pc.generar_export(db, db.get(Empresa, esc["emp"]), PER, "csv", None)
    db.rollback()
    assert db.query(ExportPlanilla).count() == antes


def test_export_schema_publicado_coincide(client, H):
    from app.export_pc import json_schema
    ruta = os.path.join(os.path.dirname(__file__), "..", "app", "contracts", "pc_asis_1_2.schema.json")
    with open(ruta, encoding="utf-8") as f:
        assert json.load(f) == json_schema(), "regenerar app/contracts/pc_asis_1_2.schema.json"
    assert client.get("/reportes/export-planilla-core/contrato", headers=H["rrhh"]).json() == json_schema()


def test_export_versiones_alcance(client, H, esc):
    assert client.get("/reportes/export-planilla-core/versiones", headers=H["rrhh_gcb"],
                      params={"empresa_id": esc["emp"]}).status_code == 403
    assert client.get("/reportes/export-planilla-core/versiones", headers=H["jefe"],
                      params={"empresa_id": esc["emp"]}).status_code == 403
    assert client.get("/reportes/export-planilla-core/versiones/999999", headers=H["rrhh"]).status_code == 404


def test_export_lote_por_empresa_del_alcance(client, H, esc):
    r = client.post("/reportes/export-planilla-core/lote", headers=H["rrhh_gcb"], params={"periodo": PER})
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["estado"] == "ok" and [a["empresa_id"] for a in t["resultado"]["archivos"]] == [esc["otra"]]
    r = client.post("/reportes/export-planilla-core/lote", headers=H["admin"], params={"periodo": PER, "formato": "json"})
    t = r.json()
    assert t["estado"] == "ok" and t["progreso"] == t["total"] == len(t["resultado"]["archivos"]) >= 2
    assert t["porcentaje"] == 100
    again = client.post("/reportes/export-planilla-core/lote", headers=H["admin"],
                        params={"periodo": PER, "formato": "json"}).json()
    assert all(a["reutilizada"] for a in again["resultado"]["archivos"])  # idempotente por empresa
    v = client.get(f"/trabajos/{t['id']}", headers=H["admin"]).json()
    assert v["estado"] == "ok"
    assert client.get(f"/trabajos/{t['id']}", headers=H["rrhh_gcb"]).status_code == 403
    assert client.get(f"/trabajos/{t['id']}", headers=H["trabajador"]).status_code == 403
    assert client.get("/trabajos/999999", headers=H["admin"]).status_code == 404
    assert any(x["id"] == t["id"] for x in client.get("/trabajos", headers=H["admin"]).json())


# ---------------------------------------------------------------- (b) trabajos
def test_recalculo_pequeno_es_sync(client, H, esc):
    r = client.post("/periodos/recalcular", headers=H["rrhh"],
                    params={"empresa_id": esc["emp"], "periodo": PER, "trabajador_id": esc["tid"]}).json()
    assert r["trabajo"] is None and r["trabajadores_recalculados"] == 1


def test_recalculo_grande_va_a_trabajo(client, H, esc, monkeypatch):
    monkeypatch.setattr(settings, "jobs_umbral_sync", 0)
    r = client.post("/periodos/recalcular", headers=H["rrhh"], params={"empresa_id": esc["emp"], "periodo": "2027-03"})
    assert r.status_code == 200, r.text
    t = r.json()["trabajo"]
    assert t["tipo"] == "recalcular" and t["modo"] == "inline" and t["estado"] == "ok"
    assert t["total"] > 0 and t["progreso"] == t["total"]
    assert r.json()["trabajadores_recalculados"] == t["resultado"]["trabajadores_recalculados"]


def test_encolar_rq_y_fallback_sin_redis(db, monkeypatch):
    monkeypatch.setattr(settings, "jobs_modo", "rq")
    encolados = []

    class Q:
        def enqueue(self, fn, *a, **k):
            encolados.append((fn, a))

    monkeypatch.setattr(trabajos, "_cola", lambda: Q())
    t = trabajos.crear(db, "export_lote", {"periodo": PER, "formato": "csv", "empresas": []}, None)
    assert trabajos.encolar(t.id) == "rq" and encolados == [("app.trabajos.ejecutar", (t.id,))]
    db.refresh(t)
    assert t.estado == "pendiente"
    trabajos.ejecutar(t.id)  # lo que haria el worker
    db.refresh(t)
    assert t.estado == "ok"

    def sin_redis():
        raise ConnectionError("redis caido")

    monkeypatch.setattr(trabajos, "_cola", sin_redis)
    t2 = trabajos.crear(db, "export_lote", {"periodo": PER, "formato": "csv", "empresas": []}, None)
    assert trabajos.encolar(t2.id) == "inline_sin_redis"
    db.refresh(t2)
    assert t2.estado == "ok"


def test_trabajo_con_error_queda_registrado(db):
    t = trabajos.crear(db, "export_lote", {"periodo": PER, "formato": "csv", "empresas": [987654]}, None)
    trabajos.ejecutar(t.id)
    db.refresh(t)
    assert t.estado == "error" and t.error and t.terminado_en
    trabajos.ejecutar(t.id)  # re-ejecutar uno terminado no hace nada
    db.refresh(t)
    assert t.estado == "error"


# ---------------------------------------------------------------- (c) alertas
def test_alerta_asistencia_decidida_sin_marcas(client, H, db):
    emp = _otra(db)
    t = _t(db, emp.id, 1)
    a = Asistencia(trabajador_id=t.id, dia_operativo=date(2027, 2, 10), periodo=PER, horas_programadas=8,
                   horas_trabajadas=10, rule_set_id=_rs(db, emp.id))
    db.add(a)
    db.flush()
    db.add(RegularizacionHE(asistencia_id=a.id, trabajador_id=t.id, horas_exceso=2, estado="aprobado", destino="pago"))
    db.commit()
    r = client.post("/periodos/recalcular", headers=H["rrhh"],
                    params={"empresa_id": emp.id, "periodo": PER, "trabajador_id": t.id})
    assert r.status_code == 200, r.text
    ns = client.get("/notificaciones", headers=H["rrhh"], params={"periodo": PER, "empresa_id": emp.id}).json()
    n = next(x for x in ns if x["tipo"] == "asistencia_decidida_sin_marcas" and x["datos"]["asistencia_id"] == a.id)
    assert n["activa"] and not n["leida"] and "2027-02-10" in n["mensaje"]
    # recalcular de nuevo no duplica
    client.post("/periodos/recalcular", headers=H["rrhh"],
                params={"empresa_id": emp.id, "periodo": PER, "trabajador_id": t.id})
    assert db.query(Notificacion).filter(Notificacion.clave == f"sin_marcas:{a.id}").count() == 1
    # alcance: RRHH de GCB la ve, admin la marca leida
    assert any(x["id"] == n["id"] for x in client.get("/notificaciones", headers=H["rrhh_gcb"]).json())
    c0 = client.get("/notificaciones/conteo", headers=H["admin"]).json()["no_leidas"]
    assert client.post(f"/notificaciones/{n['id']}/leida", headers=H["admin"]).json()["leida"] is True
    assert client.get("/notificaciones/conteo", headers=H["admin"]).json()["no_leidas"] == c0 - 1
    assert client.post("/notificaciones/999999/leida", headers=H["admin"]).status_code == 404


def test_alertas_generadas_cierre_bonos_pt(client, H, db, esc):
    from app.alertas import generar
    cav = esc["emp"]
    adm = db.execute(__import__("sqlalchemy").text("select id from usuario where email='admin@demo.gcb.pe'")).scalar()
    pt = db.query(Trabajador).filter(Trabajador.empresa_id == cav).all()
    from app.models import TipoContrato
    pt = next(t for t in pt if db.get(TipoContrato, t.tipo_contrato_id).codigo in ("PT85", "PT102"))
    for i in range(3):  # semana 8-feb: 3 dias x 6 h -> promedio 6 > 4
        db.add(Asistencia(trabajador_id=pt.id, dia_operativo=date(2027, 2, 8) + timedelta(days=i), periodo=PER,
                          horas_programadas=4, horas_trabajadas=6, rule_set_id=_rs(db, cav)))
    db.add(BonoNocturno(trabajador_id=pt.id, periodo=PER, cantidad=1, estado="registrado", registrado_por=adm))
    a = Asistencia(trabajador_id=pt.id, dia_operativo=date(2027, 2, 20), periodo=PER, horas_programadas=4,
                   horas_trabajadas=5, rule_set_id=_rs(db, cav))
    db.add(a)
    db.flush()
    db.add(RegularizacionHE(asistencia_id=a.id, trabajador_id=pt.id, horas_exceso=1))
    db.commit()
    lejos = generar(db, cav, PER, hoy=date(2027, 2, 1))
    db.commit()
    assert "pendientes_cierre" not in lejos and lejos["bonos_sin_aprobar"] == 1 and lejos["pt_riesgo"] >= 1
    cerca = generar(db, cav, PER, hoy=date(2027, 2, 25))
    db.commit()
    assert cerca["pendientes_cierre"] == 1
    assert generar(db, cav, PER, hoy=date(2027, 2, 25)) == cerca  # idempotente
    n = db.query(Notificacion).filter(Notificacion.clave == f"pendientes_cierre:{cav}:{PER}").one()
    assert n.datos["he_sin_decidir"] >= 1 and "proximo" in n.mensaje
    # se resuelve la condicion -> la alerta queda inactiva
    db.query(BonoNocturno).filter(BonoNocturno.trabajador_id == pt.id, BonoNocturno.periodo == PER,
                                  BonoNocturno.estado == "registrado").update({"estado": "rechazado"})
    db.commit()
    assert "bonos_sin_aprobar" not in generar(db, cav, PER, hoy=date(2027, 2, 1))
    db.commit()
    # endpoint
    r = client.post("/notificaciones/generar", headers=H["rrhh"], params={"periodo": PER, "empresa_id": cav})
    assert r.status_code == 200 and str(cav) in r.json()["activas_por_empresa"]
    ns = client.get("/notificaciones", headers=H["rrhh"], params={"periodo": PER, "empresa_id": cav}).json()
    assert any(x["tipo"] == "pt_riesgo" for x in ns)
    assert client.get("/notificaciones", headers=H["rrhh_gcb"], params={"empresa_id": cav}).status_code == 403
    assert client.get("/notificaciones", headers=H["jefe"]).status_code == 403
    assert client.post("/notificaciones/generar", headers=H["trabajador"], params={"periodo": PER}).status_code == 403


# ---------------------------------------------------------------- (d) seed + ventana nocturna
def test_seed_parking_tiene_horario_semana_actual(db):
    from app.models import Unidad
    hoy = date.today()
    sem = hoy - timedelta(days=hoy.weekday())
    par = db.query(Unidad).filter(Unidad.nombre.ilike("%parking%")).first()
    tids = [t.id for t in db.query(Trabajador).filter(Trabajador.unidad_id == par.id, Trabajador.activo)]
    assert db.query(HorarioPlan).filter(HorarioPlan.trabajador_id.in_(tids), HorarioPlan.semana_inicio == sem).count() >= 1


def test_ventana_nocturna_desde_config(client, H, esc, db, monkeypatch):
    from app.routers import bandeja, reportes
    j = client.get("/reportes/consolidado-mensual", headers=H["rrhh"],
                   params={"periodo": PER, "empresa_id": esc["emp"]}).json()
    assert j["ventana_nocturna"] == "22:00-06:00"
    csv = client.get("/reportes/consolidado-mensual", headers=H["rrhh"],
                     params={"periodo": PER, "empresa_id": esc["emp"], "formato": "csv"}).text
    assert "Horas nocturnas 22:00-06:00" in csv.splitlines()[0]
    monkeypatch.setattr(bandeja, "_reglas", lambda db, e, d: {"nocturno": {"inicio": "21:00", "fin": "05:00"}})
    assert reportes.ventana_nocturna(db, esc["emp"], date(2027, 2, 28)) == "21:00-05:00"
    assert reportes.conceptos(db, esc["emp"], date(2027, 2, 28))["HNOC"]["descripcion"] == "Horas nocturnas 21:00-05:00"
    assert dict(reportes.columnas("21:00-05:00"))["horas_nocturnas"] == "Horas nocturnas 21:00-05:00"
