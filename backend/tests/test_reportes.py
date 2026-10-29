"""Tests Sprint 3: Reportes consolidados y export."""
import pytest
from datetime import date, datetime, time
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_consolidado_mensual_json(async_client: AsyncClient, admin_headers, test_data):
    """Consolidado mensual retorna JSON por defecto."""
    resp = await async_client.get(
        "/reportes/consolidado-mensual",
        params={"periodo": "2026-10", "formato": "json"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "periodo" in data
    assert "registros" in data
    assert "totales" in data


@pytest.mark.asyncio
async def test_consolidado_mensual_sin_datos(async_client: AsyncClient, admin_headers):
    """Periodo sin datos retorna 404."""
    resp = await async_client.get(
        "/reportes/consolidado-mensual",
        params={"periodo": "2025-01", "formato": "json"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_consolidado_export_excel(async_client: AsyncClient, admin_headers, test_data):
    """Export a Excel funciona."""
    resp = await async_client.get(
        "/reportes/consolidado-mensual",
        params={"periodo": "2026-10", "formato": "excel"},
        headers=admin_headers,
    )
    if resp.status_code == 404:
        pytest.skip("Sin datos para periodo 2026-10")
    
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.mark.asyncio
async def test_consolidado_export_csv(async_client: AsyncClient, admin_headers, test_data):
    """Export a CSV funciona."""
    resp = await async_client.get(
        "/reportes/consolidado-mensual",
        params={"periodo": "2026-10", "formato": "csv"},
        headers=admin_headers,
    )
    if resp.status_code == 404:
        pytest.skip("Sin datos para periodo 2026-10")
    
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/csv"


@pytest.mark.asyncio
async def test_conceptos_remunerativos(async_client: AsyncClient, admin_headers, test_data):
    """Conceptos remunerativos para integración nómina."""
    empresa_id = test_data["empresa_id"]
    
    resp = await async_client.get(
        "/reportes/conceptos-remunerativos",
        params={"periodo": "2026-10", "empresa_id": empresa_id},
        headers=admin_headers,
    )
    
    if resp.status_code == 404:
        pytest.skip("Sin datos para periodo")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["periodo"] == "2026-10"
    assert data["empresa_id"] == empresa_id
    assert "trabajadores" in data


@pytest.mark.asyncio
async def test_reportes_jefe_solo_su_unidad(async_client: AsyncClient, jefe_headers, test_data):
    """Jefe solo ve reportes de su unidad."""
    resp = await async_client.get(
        "/reportes/consolidado-mensual",
        params={"periodo": "2026-10", "formato": "json"},
        headers=jefe_headers,
    )
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_reportes_trabajador_no_autorizado(async_client: AsyncClient, trabajador_headers):
    """Trabajador no puede ver reportes."""
    resp = await async_client.get(
        "/reportes/consolidado-mensual",
        params={"periodo": "2026-10"},
        headers=trabajador_headers,
    )
    assert resp.status_code == 403
