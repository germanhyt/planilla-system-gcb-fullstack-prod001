"""Sprint 4: API de programación de horas extra (HE preautorizadas por el jefe)."""


def _trab(client, H, codigo):
    return next(t for t in client.get("/trabajadores", headers=H["admin"]).json() if t["codigo"] == codigo)


def test_jefe_programa_su_unidad_upsert_y_anula(client, H):
    t = _trab(client, H, "CAV-010")
    body = {"trabajador_id": t["id"], "dia": "2025-02-10", "horas": 2, "motivo": "Evento"}
    r = client.post("/he-programadas", json=body, headers=H["jefe"])
    assert r.status_code == 200, r.text
    hid = r.json()["id"]
    # upsert: misma persona y día -> misma fila, horas actualizadas
    r2 = client.post("/he-programadas", json=body | {"horas": 3}, headers=H["jefe"])
    assert (r2.json()["id"], r2.json()["horas"]) == (hid, 3.0)
    lista = client.get("/he-programadas?desde=2025-02-01&hasta=2025-02-28", headers=H["jefe"]).json()
    assert [(x["id"], x["horas"]) for x in lista if x["trabajador_id"] == t["id"]] == [(hid, 3.0)]
    assert client.delete(f"/he-programadas/{hid}", headers=H["jefe"]).json()["estado"] == "anulada"
    lista = client.get("/he-programadas?desde=2025-02-01&hasta=2025-02-28", headers=H["jefe"]).json()
    assert all(x["id"] != hid for x in lista)


def test_alcance_por_rol(client, H):
    cav, par = _trab(client, H, "CAV-011"), _trab(client, H, "PAR-002")
    body = {"trabajador_id": par["id"], "dia": "2025-02-11", "horas": 1}
    assert client.post("/he-programadas", json=body, headers=H["jefe"]).status_code == 403
    assert client.post("/he-programadas", json=body, headers=H["trabajador"]).status_code == 403
    assert client.post("/he-programadas", json=body, headers=H["rrhh"]).status_code == 200
    assert client.post("/he-programadas", json=body | {"trabajador_id": cav["id"]}, headers=H["admin"]).status_code == 200
    # el jefe de Cavas no ve las de Parking
    lista = client.get("/he-programadas?desde=2025-02-11&hasta=2025-02-11", headers=H["jefe"]).json()
    assert {x["trabajador_id"] for x in lista} == {cav["id"]}
    assert client.post("/he-programadas", json=body | {"horas": 0}, headers=H["rrhh"]).status_code == 422
    assert client.post("/he-programadas", json=body | {"horas": 13}, headers=H["rrhh"]).status_code == 422


def test_bloqueo_en_periodo_cerrado(client, H, ids):
    t = _trab(client, H, "CAV-012")
    body = {"trabajador_id": t["id"], "dia": "2024-05-15", "horas": 1}
    hid = client.post("/he-programadas", json=body, headers=H["jefe"]).json()["id"]
    c = client.post("/periodos/cerrar", json={"empresa_id": ids["emp"]["CAVAS"], "periodo": "2024-05", "confirmar": True},
                    headers=H["rrhh"])
    assert c.status_code == 200, c.text
    try:
        assert client.post("/he-programadas", json=body | {"horas": 2}, headers=H["jefe"]).status_code == 409
        assert client.delete(f"/he-programadas/{hid}", headers=H["jefe"]).status_code == 409
    finally:
        client.post(f"/periodos/reabrir/{c.json()['id']}", json={"razon_reapertura": "test he programadas"},
                    headers=H["admin"])
