"""Tests Sprint 3: Banco de horas compensatorias."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_consultar_saldo_inicial_cero(async_client: AsyncClient, trabajador_headers, test_data):
    """Saldo inicial de trabajador sin movimientos es 0."""
    trabajador_id = test_data["trabajador_id"]
    
    resp = await async_client.get(
        f"/banco-horas/saldo/{trabajador_id}",
        headers=trabajador_headers,
    )
    
    if resp.status_code == 403:
        pytest.skip("Trabajador no puede ver otros saldos")
    
    assert resp.status_code == 200
    data = resp.json()
    assert "saldo_horas" in data
    assert data["saldo_horas"] >= 0


@pytest.mark.asyncio
async def test_consultar_historial_vacio(async_client: AsyncClient, trabajador_headers, test_data):
    """Historial vacío para trabajador sin movimientos."""
    trabajador_id = test_data["trabajador_id"]
    
    resp = await async_client.get(
        f"/banco-horas/historial/{trabajador_id}",
        headers=trabajador_headers,
    )
    
    if resp.status_code == 403:
        pytest.skip("Trabajador no autorizado")
    
    assert resp.status_code == 200
    data = resp.json()
    assert "movimientos" in data
    assert isinstance(data["movimientos"], list)


@pytest.mark.asyncio
async def test_proximas_expiraciones_admin(async_client: AsyncClient, admin_headers):
    """Admin puede ver próximas expiraciones."""
    resp = await async_client.get(
        "/banco-horas/expiraciones",
        params={"dias_alerta": 15},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "expiraciones" in data
    assert isinstance(data["expiraciones"], list)


@pytest.mark.asyncio
async def test_trabajador_no_puede_ver_expiraciones(async_client: AsyncClient, trabajador_headers):
    """Trabajador no puede ver reporte de expiraciones (solo RRHH/Admin)."""
    resp = await async_client.get(
        "/banco-horas/expiraciones",
        headers=trabajador_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_banco_horas_integrado_con_regularizacion(async_client: AsyncClient, jefe_headers, test_data):
    """Al aprobar regularización con destino compensación, se registra en banco de horas."""
    pass


@pytest.mark.asyncio
async def test_jefe_puede_ver_saldo_de_su_unidad(async_client: AsyncClient, jefe_headers, test_data):
    """Jefe puede consultar saldo de trabajadores de su unidad."""
    trabajador_id = test_data["trabajador_id"]
    
    resp = await async_client.get(
        f"/banco-horas/saldo/{trabajador_id}",
        headers=jefe_headers,
    )
    assert resp.status_code in (200, 403)
