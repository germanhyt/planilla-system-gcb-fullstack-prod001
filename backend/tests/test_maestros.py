def test_seed_estructura(client, H):
    emp = {e["razon_social"] for e in client.get("/empresas", headers=H["admin"]).json()}
    assert {"CAVAS SAC", "GCB SA"} <= emp
    tcs = {t["codigo"]: t for t in client.get("/tipos-contrato", headers=H["admin"]).json()}
    assert tcs["PT85"]["horas_mes"] == 85 and tcs["PT102"]["horas_mes"] == 102 and tcs["FT"]["jornada_diaria_min"] == 480
    trab = client.get("/trabajadores", headers=H["rrhh"]).json()
    assert len([t for t in trab if t["codigo"].startswith("CAV-")]) == 32
    assert all(t["doc_tipo"] == "FICT" for t in trab if t["codigo"][:4] in ("CAV-", "PAR-"))


def test_crud_sede_geocerca(client, H, ids):
    r = client.post("/sedes", headers=H["admin"], json={"unidad_id": ids["uni"]["REF"], "nombre": "Anexo", "lat": -9.5, "lng": -77.5,
                                                         "radio_geocerca_m": 120})
    assert r.status_code == 201
    s = r.json()
    assert s["radio_geocerca_m"] == 120 and s["lat"] == -9.5
    upd = {k: v for k, v in s.items() if k != "id"} | {"radio_geocerca_m": 200}
    assert client.put(f"/sedes/{s['id']}", headers=H["admin"], json=upd).json()["radio_geocerca_m"] == 200
    assert client.post("/sedes", headers=H["admin"], json={"unidad_id": 1, "nombre": "X", "lat": 200, "lng": 0}).status_code == 422
    client.delete(f"/sedes/{s['id']}", headers=H["admin"])
    assert s["id"] not in [x["id"] for x in client.get("/sedes", headers=H["admin"]).json()]
    assert s["id"] in [x["id"] for x in client.get("/sedes?incluir_inactivos=true", headers=H["admin"]).json()]


def test_tipo_contrato_configurable_y_override_jornada(client, H, ids):
    r = client.post("/tipos-contrato", headers=H["rrhh"], json={"codigo": "PT60", "nombre": "PT 60", "horas_mes": 60,
                                                                 "jornada_diaria_min": 180, "es_part_time": True})
    assert r.status_code == 201
    t = client.post("/trabajadores", headers=H["rrhh"], json={
        "codigo": "JOR-1", "empresa_id": ids["emp"]["GCBSA"], "unidad_id": ids["uni"]["REF"], "doc_tipo": "FICT", "doc_numero": "J1",
        "nombres": "N", "apellidos": "A", "tipo_contrato_id": r.json()["id"], "jornada_diaria_min": 200, "fecha_ingreso": "2026-03-01"})
    assert t.status_code == 201 and t.json()["jornada_diaria_min"] == 200


def test_unicidad_documento(client, H, ids):
    body = {"codigo": "DUP-1", "empresa_id": ids["emp"]["CAVAS"], "unidad_id": ids["uni"]["SISA"], "doc_tipo": "FICT",
            "doc_numero": "X0000001", "nombres": "N", "apellidos": "A", "tipo_contrato_id": ids["tc"]["FT"], "fecha_ingreso": "2026-01-01"}
    assert client.post("/trabajadores", headers=H["rrhh"], json=body).status_code == 409


def test_ruc_valido(client, H):
    assert client.post("/empresas", headers=H["admin"], json={"codigo": "R", "razon_social": "R", "ruc": "123"}).status_code == 422


def test_turnos_semilla_cruzan_medianoche(client, H):
    ts = client.get("/turnos-plantilla", headers=H["jefe"]).json()
    assert sum(1 for t in ts if t["fin"] < t["inicio"]) >= 5
