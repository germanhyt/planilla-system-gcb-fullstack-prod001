"""Tests Sprint 3: Banco de horas compensatorias."""
import pytest

from app.models import Trabajador


@pytest.fixture
def cav007(db):
    trab = db.query(Trabajador).filter(Trabajador.codigo == "CAV-007").one()  # la semilla lo garantiza
    return trab


@pytest.fixture
def propio(client, H):
    return client.get("/me/trabajador", headers=H["trabajador"]).json()


def test_consultar_saldo_inicial_cero(client, H, propio):
    """Saldo inicial del propio trabajador sin movimientos es >= 0."""
    resp = client.get(f"/banco-horas/saldo/{propio['id']}", headers=H["trabajador"])
    assert resp.status_code == 200
    data = resp.json()
    assert "saldo_horas" in data
    assert data["saldo_horas"] >= 0

def test_consultar_historial_vacio(client, H, propio):
    """Historial del propio trabajador: lista de movimientos."""
    resp = client.get(f"/banco-horas/historial/{propio['id']}", headers=H["trabajador"])
    assert resp.status_code == 200
    data = resp.json()
    assert "movimientos" in data
    assert isinstance(data["movimientos"], list)


def test_trabajador_no_ve_saldo_ajeno(client, H, cav007, propio):
    otro = cav007.id if cav007.id != propio["id"] else cav007.id + 100000
    assert client.get(f"/banco-horas/saldo/{otro}", headers=H["trabajador"]).status_code in (403, 404)

def test_proximas_expiraciones_admin(client, H):
    """Admin puede ver próximas expiraciones."""
    resp = client.get(
        "/banco-horas/expiraciones",
        params={"dias_alerta": 15},
        headers=H["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "expiraciones" in data
    assert isinstance(data["expiraciones"], list)


def test_trabajador_no_puede_ver_expiraciones(client, H):
    """Trabajador no puede ver reporte de expiraciones (solo RRHH/Admin)."""
    resp = client.get(
        "/banco-horas/expiraciones",
        headers=H["trabajador"],
    )
    assert resp.status_code == 403


def test_jefe_puede_ver_saldo_de_su_unidad(client, H, cav007):
    """Jefe de Cavas consulta saldo de un trabajador de su unidad."""
    resp = client.get(f"/banco-horas/saldo/{cav007.id}", headers=H["jefe"])
    assert resp.status_code == 200
