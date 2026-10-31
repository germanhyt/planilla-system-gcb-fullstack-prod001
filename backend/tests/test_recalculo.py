"""Sprint 4: recálculo (endpoint) y disparo automático al cambiar HE programadas u horarios."""
from datetime import datetime

from zoneinfo import ZoneInfo

from app.models import Asistencia, Marca

LIMA = ZoneInfo("America/Lima")


def _trab(client, H, codigo):
    return next(t for t in client.get("/trabajadores", headers=H["admin"]).json() if t["codigo"] == codigo)


def _marcar(db, tid, y, m, d):
    db.add_all([
        Marca(trabajador_id=tid, tipo="entrada", ts_servidor=datetime(y, m, d, 8, tzinfo=LIMA), metodo="gps",
              validacion_estado="ok"),
        Marca(trabajador_id=tid, tipo="salida", ts_servidor=datetime(y, m, d, 20, tzinfo=LIMA), metodo="gps",
              validacion_estado="ok"),
    ])
    db.commit()


def _asis(db, tid, dia):
    db.expire_all()
    return db.query(Asistencia).filter_by(trabajador_id=tid, dia_operativo=dia).first()


def test_programar_he_dispara_recalculo(client, H, db):
    from datetime import date
    t = _trab(client, H, "CAV-013")
    _marcar(db, t["id"], 2026, 3, 16)
    r = client.post("/he-programadas", json={"trabajador_id": t["id"], "dia": "2026-03-16", "horas": 2},
                    headers=H["jefe"])
    assert r.status_code == 200, r.text
    a = _asis(db, t["id"], date(2026, 3, 16))
    assert a is not None and float(a.horas_extra_programadas) == 2.0
    client.delete(f"/he-programadas/{r.json()['id']}", headers=H["jefe"])
    assert float(_asis(db, t["id"], date(2026, 3, 16)).horas_extra_programadas) == 0.0


def test_endpoint_recalcular_permisos_y_cerrado(client, H):
    emp = _trab(client, H, "CAV-013")["empresa_id"]
    q = f"/periodos/recalcular?empresa_id={emp}&periodo=2026-03"
    assert client.post(q, headers=H["jefe"]).status_code == 403
    r = client.post(q, headers=H["rrhh"])
    assert r.status_code == 200, r.text
    assert r.json()["trabajadores_recalculados"] >= 1
    cerrar = client.post("/periodos/cerrar", json={"empresa_id": emp, "periodo": "2023-03", "confirmar": True},
                         headers=H["admin"])
    assert cerrar.status_code in (200, 409), cerrar.text
    r = client.post(f"/periodos/recalcular?empresa_id={emp}&periodo=2023-03", headers=H["admin"])
    assert r.status_code == 409
