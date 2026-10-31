from conftest import PW


def test_login_ok_por_rol(client):
    for rol in ("admin", "rrhh", "jefe", "trabajador"):
        r = client.post("/auth/login", json={"email": f"{rol}@demo.gcb.pe", "password": PW})
        assert r.status_code == 200 and r.json()["rol"] == rol


def test_login_fallido(client):
    assert client.post("/auth/login", json={"email": "admin@demo.gcb.pe", "password": "malaclave"}).status_code == 401
    assert client.post("/auth/login", json={"email": "noexiste@demo.gcb.pe", "password": "x"}).status_code == 401


def test_sin_token_o_token_invalido(client):
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_password_hash_argon2_no_expuesto(client, H):
    me = client.get("/me", headers=H["admin"]).json()
    assert "password_hash" not in me and me["rol"] == "admin"


def test_perfil_editable(client, H):
    r = client.put("/me", headers=H["trabajador"], json={"telefono": "999000111", "idioma": "es"})
    assert r.status_code == 200 and r.json()["telefono"] == "999000111"


def test_trabajador_ve_su_ficha(client, H):
    r = client.get("/me/trabajador", headers=H["trabajador"])
    assert r.status_code == 200 and r.json()["codigo"] == "CAV-007"


def test_usuario_inactivo_no_entra(client, H):
    u = client.post("/usuarios", headers=H["admin"], json={"email": "baja@demo.gcb.pe", "password": "Temporal123",
                                                            "rol": "trabajador", "nombre": "Baja"}).json()
    assert client.post("/auth/login", json={"email": "baja@demo.gcb.pe", "password": "Temporal123"}).status_code == 200
    client.put(f"/usuarios/{u['id']}", headers=H["admin"], json={"activo": False})
    assert client.post("/auth/login", json={"email": "baja@demo.gcb.pe", "password": "Temporal123"}).status_code == 401


def test_cambio_password(client, H):
    client.post("/usuarios", headers=H["admin"], json={"email": "pw@demo.gcb.pe", "password": "Inicial123",
                                                        "rol": "trabajador", "nombre": "PW"})
    t = client.post("/auth/login", json={"email": "pw@demo.gcb.pe", "password": "Inicial123"}).json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    assert client.post("/me/password", headers=h, json={"actual": "mala", "nueva": "Nueva12345"}).status_code == 400
    assert client.post("/me/password", headers=h, json={"actual": "Inicial123", "nueva": "Nueva12345"}).status_code == 200
    assert client.post("/auth/login", json={"email": "pw@demo.gcb.pe", "password": "Nueva12345"}).status_code == 200
