"""Sprint 4: justificación de faltas (trabajador solicita, jefe aprueba/rechaza, sin duplicados)."""
from datetime import date, timedelta

from app.models import HorarioAsignacion, TurnoPlantilla, Usuario


def _trab(client, H, codigo):
    return next(t for t in client.get("/trabajadores", headers=H["admin"]).json() if t["codigo"] == codigo)


def test_flujo_trabajador_solicita_jefe_aprueba_y_sin_duplicados(client, H):
    yo = _trab(client, H, "CAV-007")
    body = {"trabajador_id": yo["id"], "dia": "2025-11-07", "motivo": "licencia_medica", "descripcion": "Cita médica"}
    r = client.post("/justificaciones", json=body, headers=H["trabajador"])
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    assert r.json()["estado"] == "pendiente"
    # duplicado (pendiente) -> 409, incluso desde el jefe o por la ruta Sprint 3
    assert client.post("/justificaciones", json=body, headers=H["trabajador"]).status_code == 409
    assert client.post("/excepciones/justificar-falta", json=body, headers=H["jefe"]).status_code == 409
    # el jefe ve la pendiente de su unidad
    pend = client.get("/justificaciones?estado=pendiente", headers=H["jefe"]).json()
    assert fid in [p["id"] for p in pend]
    # el trabajador no puede decidir
    assert client.post(f"/justificaciones/{fid}/decidir", json={"aprobar": True}, headers=H["trabajador"]).status_code == 403
    d = client.post(f"/justificaciones/{fid}/decidir", json={"aprobar": True, "comentario": "ok"}, headers=H["jefe"])
    assert (d.status_code, d.json()["estado"]) == (200, "aprobada")
    # ya decidida: no se re-decide ni se retira; sigue sin admitir duplicado
    assert client.post(f"/justificaciones/{fid}/decidir", json={"aprobar": False}, headers=H["jefe"]).status_code == 409
    assert client.delete(f"/justificaciones/{fid}", headers=H["trabajador"]).status_code == 409
    assert client.post("/justificaciones", json=body, headers=H["trabajador"]).status_code == 409


def test_rechazada_permite_nueva_solicitud_y_retiro(client, H):
    yo = _trab(client, H, "CAV-007")
    body = {"trabajador_id": yo["id"], "dia": "2025-11-08", "motivo": "permiso"}
    fid = client.post("/justificaciones", json=body, headers=H["trabajador"]).json()["id"]
    assert client.post(f"/justificaciones/{fid}/decidir", json={"aprobar": False, "comentario": "sin sustento"},
                       headers=H["rrhh"]).json()["estado"] == "rechazada"
    r = client.post("/justificaciones", json=body | {"descripcion": "con constancia"}, headers=H["trabajador"])
    assert r.status_code == 201, r.text
    assert client.delete(f"/justificaciones/{r.json()['id']}", headers=H["trabajador"]).json() == {"ok": True}
    mias = client.get("/justificaciones?desde=2025-11-08&hasta=2025-11-08", headers=H["trabajador"]).json()
    assert [m["estado"] for m in mias] == ["rechazada"]


def test_alcance_por_rol(client, H):
    otro, par = _trab(client, H, "CAV-016"), _trab(client, H, "PAR-004")
    b = {"dia": "2025-11-09", "motivo": "otro"}
    assert client.post("/justificaciones", json=b | {"trabajador_id": otro["id"]}, headers=H["trabajador"]).status_code == 403
    assert client.post("/justificaciones", json=b | {"trabajador_id": par["id"]}, headers=H["jefe"]).status_code == 403
    r = client.post("/justificaciones", json=b | {"trabajador_id": par["id"]}, headers=H["jefe_parking"])
    assert (r.status_code, r.json()["estado"]) == (201, "aprobada")   # registro directo del jefe
    assert all(x["trabajador_id"] != par["id"] for x in client.get("/justificaciones", headers=H["jefe"]).json())


def test_bloqueo_periodo_cerrado(client, H, ids):
    yo = _trab(client, H, "CAV-007")
    c = client.post("/periodos/cerrar", json={"empresa_id": ids["emp"]["CAVAS"], "periodo": "2024-07", "confirmar": True},
                    headers=H["rrhh"])
    assert c.status_code == 200, c.text
    try:
        r = client.post("/justificaciones", json={"trabajador_id": yo["id"], "dia": "2024-07-03", "motivo": "permiso"},
                        headers=H["trabajador"])
        assert r.status_code == 409
    finally:
        client.post(f"/periodos/reabrir/{c.json()['id']}", json={"razon_reapertura": "test justificaciones"},
                    headers=H["admin"])


def test_faltas_sin_justificar_usa_asignacion_y_omite_aprobadas(client, H, db):
    t = _trab(client, H, "CAV-017")
    p = db.query(TurnoPlantilla).filter(TurnoPlantilla.unidad_id == t["unidad_id"]).first()
    lunes = date(2025, 12, 1)
    db.add(HorarioAsignacion(trabajador_id=t["id"], vigente_desde=lunes, vigente_hasta=lunes + timedelta(days=2),
                             patron=[[p.id] * 7], creado_por=db.query(Usuario).first().id))
    db.commit()
    dias = lambda **kw: sorted(f["dia"] for f in client.get(  # noqa: E731
        "/excepciones/faltas-sin-justificar", params={"periodo": "2025-12", **kw}, headers=H["jefe"]).json()
        if f["trabajador_id"] == t["id"])
    assert dias() == ["2025-12-01", "2025-12-02", "2025-12-03"]
    r = client.post("/justificaciones", json={"trabajador_id": t["id"], "dia": "2025-12-02", "motivo": "vacaciones"},
                    headers=H["jefe"])
    assert r.status_code == 201, r.text
    assert dias() == ["2025-12-01", "2025-12-03"]
    assert dias(incluir_justificadas=True) == ["2025-12-01", "2025-12-02", "2025-12-03"]
