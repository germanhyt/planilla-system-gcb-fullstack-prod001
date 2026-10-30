def test_flujo_bono_3am(client, H, ids):
    t = client.get("/trabajadores", headers=H["rrhh"]).json()[0]
    assert client.post("/bonos-nocturnos", headers=H["rrhh"], json={"trabajador_id": t["id"], "periodo": "2026-10", "cantidad": 4}).status_code == 403
    b = client.post("/bonos-nocturnos", headers=H["admin"], json={"trabajador_id": t["id"], "periodo": "2026-10", "cantidad": 4}).json()
    assert b["estado"] == "registrado"
    assert client.post(f"/bonos-nocturnos/{b['id']}/decision", headers=H["admin"], json={"aprobar": True}).status_code == 403
    b2 = client.post("/bonos-nocturnos", headers=H["admin"], json={"trabajador_id": t["id"], "periodo": "2026-10", "cantidad": 5, "monto": 50}).json()
    assert b2["id"] == b["id"] and b2["cantidad"] == 5
    ok = client.post(f"/bonos-nocturnos/{b['id']}/decision", headers=H["rrhh"], json={"aprobar": True, "comentario": "ok"})
    assert ok.status_code == 200 and ok.json()["estado"] == "aprobado"
    assert client.post(f"/bonos-nocturnos/{b['id']}/decision", headers=H["rrhh"], json={"aprobar": False}).status_code == 409
    h = client.get(f"/bonos-nocturnos/{b['id']}/historial", headers=H["rrhh"]).json()
    assert [x["accion"] for x in h] == ["registrar", "corregir", "aprobado"] and [x["cantidad"] for x in h] == [4, 5, 5]
