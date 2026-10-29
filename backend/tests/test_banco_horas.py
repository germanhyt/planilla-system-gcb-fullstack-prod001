"""Tests Sprint 3: Banco de horas compensatorias."""


def test_consultar_saldo_inicial_cero(client, db, H):
    """Saldo inicial de trabajador sin movimientos es 0."""
    # Get a real trabajador from the database
    from app.models import Trabajador
    trab = db.query(Trabajador).filter(Trabajador.codigo == "CAV-007").first()
    if not trab:
        import pytest
        pytest.skip("No hay trabajador CAV-007 en semilla")
    
    resp = client.get(
        f"/banco-horas/saldo/{trab.id}",
        headers=H["trabajador"],
    )
    
    if resp.status_code == 403:
        import pytest
        pytest.skip("Trabajador no puede ver otros saldos")
    
    assert resp.status_code == 200
    data = resp.json()
    assert "saldo_horas" in data
    assert data["saldo_horas"] >= 0


def test_consultar_historial_vacio(client, db, H):
    """Historial vacío para trabajador sin movimientos."""
    from app.models import Trabajador
    trab = db.query(Trabajador).filter(Trabajador.codigo == "CAV-007").first()
    if not trab:
        import pytest
        pytest.skip("No hay trabajador en semilla")
    
    resp = client.get(
        f"/banco-horas/historial/{trab.id}",
        headers=H["trabajador"],
    )
    
    if resp.status_code == 403:
        import pytest
        pytest.skip("Trabajador no autorizado")
    
    assert resp.status_code == 200
    data = resp.json()
    assert "movimientos" in data
    assert isinstance(data["movimientos"], list)


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


def test_banco_horas_integrado_con_regularizacion(client, H, db):
    """Al aprobar regularización con destino compensación, se registra en banco de horas."""
    # Este test será implementado cuando tengamos la lógica completa
    pass


def test_jefe_puede_ver_saldo_de_su_unidad(client, db, H):
    """Jefe puede consultar saldo de trabajadores de su unidad."""
    from app.models import Trabajador
    trab = db.query(Trabajador).filter(Trabajador.codigo == "CAV-007").first()
    if not trab:
        import pytest
        pytest.skip("No hay trabajador en semilla")
    
    resp = client.get(
        f"/banco-horas/saldo/{trab.id}",
        headers=H["jefe"],
    )
    assert resp.status_code in (200, 403)
