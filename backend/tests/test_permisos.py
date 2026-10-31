import pytest


@pytest.mark.parametrize("rol,esperado", [("trabajador", 403), ("jefe", 200), ("rrhh", 200), ("admin", 200)])
def test_lectura_maestros(client, H, rol, esperado):
    assert client.get("/empresas", headers=H[rol]).status_code == esperado


@pytest.mark.parametrize("rol,esperado", [("trabajador", 403), ("jefe", 403), ("rrhh", 403), ("admin", 201)])
def test_crear_empresa_solo_admin(client, H, rol, esperado):
    ruc = {"trabajador": "20999999991", "jefe": "20999999992", "rrhh": "20999999993", "admin": "20999999994"}[rol]
    r = client.post("/empresas", headers=H[rol], json={"codigo": f"T{rol[:3]}", "razon_social": "X", "ruc": ruc})
    assert r.status_code == esperado


@pytest.mark.parametrize("rol,esperado", [("trabajador", 403), ("jefe", 403), ("rrhh", 201), ("admin", 201)])
def test_crear_trabajador_rrhh_admin(client, H, ids, rol, esperado):
    r = client.post("/trabajadores", headers=H[rol], json={
        "codigo": f"PERM-{rol}", "empresa_id": ids["emp"]["CAVAS"], "unidad_id": ids["uni"]["SISA"], "doc_tipo": "FICT",
        "doc_numero": f"P-{rol}", "nombres": "N", "apellidos": "A", "tipo_contrato_id": ids["tc"]["PT85"],
        "fecha_ingreso": "2026-01-01"})
    assert r.status_code == esperado


def test_jefe_solo_ve_su_unidad(client, H, ids):
    cav = client.get("/trabajadores", headers=H["jefe"]).json()
    assert cav and all(t["unidad_id"] == ids["uni"]["SISA"] for t in cav)
    park = client.get("/trabajadores", headers=H["jefe_parking"]).json()
    assert park and all(t["unidad_id"] == ids["uni"]["PARK"] for t in park)
    assert client.get(f"/trabajadores/{cav[0]['id']}", headers=H["jefe_parking"]).status_code == 404


def test_usuarios_y_auditoria_restringidos(client, H):
    assert client.get("/usuarios", headers=H["rrhh"]).status_code == 403
    assert client.get("/usuarios", headers=H["admin"]).status_code == 200
    assert client.get("/auditoria", headers=H["jefe"]).status_code == 403
    assert client.get("/auditoria", headers=H["rrhh"]).status_code == 200


def test_rule_set_solo_admin_escribe(client, H, ids):
    body = {"empresa_id": ids["emp"]["CAVAS"], "valid_from": "2030-01-01", "config": {}}
    assert client.post("/rule-sets", headers=H["rrhh"], json=body).status_code == 403
    assert client.get("/rule-sets", headers=H["jefe"]).status_code == 200
    assert client.get("/rule-sets", headers=H["trabajador"]).status_code == 403
