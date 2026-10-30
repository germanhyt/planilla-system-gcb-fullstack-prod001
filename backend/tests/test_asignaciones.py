"""Sprint 4: API de horario asignado con vigencia (jefe/RRHH) y calendario resuelto."""


def _trab(client, H, codigo):
    return next(t for t in client.get("/trabajadores", headers=H["admin"]).json() if t["codigo"] == codigo)


def _plantillas(client, H, unidad_id):
    return [p for p in client.get("/turnos-plantilla", headers=H["admin"]).json() if p["unidad_id"] == unidad_id]


def test_jefe_asigna_rotacion_y_la_nueva_cierra_la_anterior(client, H):
    t = _trab(client, H, "CAV-013")
    p1, p2 = _plantillas(client, H, t["unidad_id"])[:2]
    sem1 = [p1["id"]] * 5 + [None, None]
    r = client.post("/asignaciones-horario", headers=H["jefe"],
                    json={"trabajador_id": t["id"], "vigente_desde": "2025-06-02", "patron": [sem1]})
    assert r.status_code == 201, r.text
    r2 = client.post("/asignaciones-horario", headers=H["jefe"],
                     json={"trabajador_id": t["id"], "vigente_desde": "2025-06-16",
                           "patron": [sem1, [p2["id"]] * 5 + [None, None]]})
    assert r2.status_code == 201, r2.text
    lista = client.get(f"/asignaciones-horario?trabajador_id={t['id']}", headers=H["jefe"]).json()
    assert [(a["vigente_desde"], a["vigente_hasta"]) for a in lista] == [("2025-06-16", None), ("2025-06-02", "2025-06-15")]
    cal = client.get(f"/asignaciones-horario/calendario?trabajador_id={t['id']}&desde=2025-06-02&hasta=2025-06-29",
                     headers=H["jefe"]).json()
    pid = {d["dia"]: d["plantilla_id"] for d in cal["dias"]}
    assert (pid["2025-06-02"], pid["2025-06-07"], pid["2025-06-16"], pid["2025-06-23"]) == (p1["id"], None, p1["id"], p2["id"])
    assert cal["contrato"] and cal["jornada_diaria_min"]
    assert all("horas_programadas" in d for d in cal["dias"] if d["plantilla_id"])
    assert client.delete(f"/asignaciones-horario/{r2.json()['id']}", headers=H["jefe"]).json() == {"ok": True}


def test_alcance_y_validaciones(client, H):
    cav, par = _trab(client, H, "CAV-014"), _trab(client, H, "PAR-003")
    pc = _plantillas(client, H, cav["unidad_id"])[0]
    pp = _plantillas(client, H, par["unidad_id"])[0]
    body = {"trabajador_id": par["id"], "vigente_desde": "2025-06-02", "patron": [[pp["id"]] * 7]}
    assert client.post("/asignaciones-horario", json=body, headers=H["jefe"]).status_code == 403
    assert client.post("/asignaciones-horario", json=body, headers=H["trabajador"]).status_code == 403
    assert client.post("/asignaciones-horario", json=body, headers=H["rrhh"]).status_code == 201
    assert client.get(f"/asignaciones-horario?trabajador_id={par['id']}", headers=H["jefe"]).status_code == 403
    malo = {"trabajador_id": cav["id"], "vigente_desde": "2025-06-02"}
    assert client.post("/asignaciones-horario", json=malo | {"patron": [[pc["id"]] * 6]}, headers=H["jefe"]).status_code == 422
    assert client.post("/asignaciones-horario", json=malo | {"patron": [[pp["id"]] * 7]}, headers=H["jefe"]).status_code == 422
    assert client.post("/asignaciones-horario", json=malo | {"patron": [[pc["id"]] * 7], "vigente_hasta": "2025-05-01"},
                       headers=H["jefe"]).status_code == 422


def test_trabajador_ve_su_calendario_y_bloqueo_periodo_cerrado(client, H, ids):
    yo = _trab(client, H, "CAV-007")
    otro = _trab(client, H, "CAV-015")
    assert client.get(f"/asignaciones-horario/calendario?trabajador_id={yo['id']}&desde=2025-06-01&hasta=2025-06-07",
                      headers=H["trabajador"]).status_code == 200
    assert client.get(f"/asignaciones-horario?trabajador_id={otro['id']}", headers=H["trabajador"]).status_code == 403
    p = _plantillas(client, H, otro["unidad_id"])[0]
    c = client.post("/periodos/cerrar", json={"empresa_id": ids["emp"]["CAVAS"], "periodo": "2024-06", "confirmar": True},
                    headers=H["rrhh"])
    assert c.status_code == 200, c.text
    try:
        r = client.post("/asignaciones-horario", headers=H["jefe"],
                        json={"trabajador_id": otro["id"], "vigente_desde": "2024-06-10", "patron": [[p["id"]] * 7]})
        assert r.status_code == 409
    finally:
        client.post(f"/periodos/reabrir/{c.json()['id']}", json={"razon_reapertura": "test asignaciones"},
                    headers=H["admin"])
