def _ult(client, H, **f):
    return client.get("/auditoria", headers=H["admin"], params=f).json()


def test_login_auditado(client, H):
    client.post("/auth/login", json={"email": "rrhh@demo.gcb.pe", "password": "incorrecta"})
    assert _ult(client, H, accion="login_fallido")
    assert _ult(client, H, accion="login_ok")


def test_cud_auditado_con_antes_despues(client, H, ids):
    t = client.post("/trabajadores", headers=H["rrhh"], json={
        "codigo": "AUD-1", "empresa_id": ids["emp"]["CAVAS"], "unidad_id": ids["uni"]["SISA"], "doc_tipo": "FICT",
        "doc_numero": "AUD1", "nombres": "N", "apellidos": "A", "tipo_contrato_id": ids["tc"]["FT"], "fecha_ingreso": "2026-02-01"}).json()
    upd = dict(t) | {"cargo": "Bartender"}
    upd.pop("id")
    client.put(f"/trabajadores/{t['id']}", headers=H["rrhh"], json=upd)
    client.delete(f"/trabajadores/{t['id']}", headers=H["rrhh"])
    log = _ult(client, H, entidad="trabajador", entidad_id=str(t["id"]))
    acc = [a["accion"] for a in log]
    assert acc == ["eliminar", "actualizar", "crear"]
    act = log[1]
    assert act["antes"]["cargo"] is None and act["despues"]["cargo"] == "Bartender"
    assert log[0]["despues"]["activo"] is False and all(a["usuario_id"] for a in log)


def test_password_no_en_auditoria(client, H):
    client.post("/usuarios", headers=H["admin"], json={"email": "aud@demo.gcb.pe", "password": "Secreto123",
                                                        "rol": "jefe", "nombre": "Aud"})
    a = _ult(client, H, entidad="usuario", accion="crear")[0]
    assert "password_hash" not in a["despues"] and "Secreto123" not in str(a)
