"""Tests Sprint 3: Cierre de periodos."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cerrar_periodo(async_client: AsyncClient, admin_headers, test_data):
    """Admin puede cerrar periodo."""
    empresa_id = test_data["empresa_id"]
    
    resp = await async_client.post(
        "/periodos/cerrar",
        json={"empresa_id": empresa_id, "periodo": "2026-09"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["periodo"] == "2026-09"
    assert data["estado"] == "cerrado"


@pytest.mark.asyncio
async def test_cerrar_periodo_duplicado(async_client: AsyncClient, admin_headers, test_data):
    """No se puede cerrar el mismo periodo dos veces."""
    empresa_id = test_data["empresa_id"]
    
    await async_client.post(
        "/periodos/cerrar",
        json={"empresa_id": empresa_id, "periodo": "2026-08"},
        headers=admin_headers,
    )
    
    resp = await async_client.post(
        "/periodos/cerrar",
        json={"empresa_id": empresa_id, "periodo": "2026-08"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reabrir_periodo_admin(async_client: AsyncClient, admin_headers, test_data):
    """Admin puede reabrir periodo con razón."""
    empresa_id = test_data["empresa_id"]
    
    cierre_resp = await async_client.post(
        "/periodos/cerrar",
        json={"empresa_id": empresa_id, "periodo": "2026-07"},
        headers=admin_headers,
    )
    cierre_id = cierre_resp.json()["id"]
    
    resp = await async_client.post(
        f"/periodos/reabrir/{cierre_id}",
        json={"razon_reapertura": "Corrección de errores en marcas del periodo"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["estado"] == "reabierto"
    assert data["razon_reapertura"] == "Corrección de errores en marcas del periodo"


@pytest.mark.asyncio
async def test_reabrir_periodo_rrhh_no_autorizado(async_client: AsyncClient, rrhh_headers, test_data):
    """RRHH no puede reabrir (solo admin)."""
    empresa_id = test_data["empresa_id"]
    
    cierre_resp = await async_client.post(
        "/periodos/cerrar",
        json={"empresa_id": empresa_id, "periodo": "2026-06"},
        headers=rrhh_headers,
    )
    if cierre_resp.status_code != 200:
        pytest.skip("No se pudo cerrar periodo")
    
    cierre_id = cierre_resp.json()["id"]
    
    resp = await async_client.post(
        f"/periodos/reabrir/{cierre_id}",
        json={"razon_reapertura": "Intento de reapertura"},
        headers=rrhh_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_historial_cierres(async_client: AsyncClient, admin_headers, test_data):
    """Listar histórico de cierres."""
    empresa_id = test_data["empresa_id"]
    
    await async_client.post(
        "/periodos/cerrar",
        json={"empresa_id": empresa_id, "periodo": "2026-05"},
        headers=admin_headers,
    )
    
    resp = await async_client.get(
        "/periodos/historial",
        params={"empresa_id": empresa_id},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "periodo" in data[0]
        assert "estado" in data[0]


@pytest.mark.asyncio
async def test_trabajador_no_puede_cerrar(async_client: AsyncClient, trabajador_headers, test_data):
    """Trabajador no puede cerrar periodos."""
    resp = await async_client.post(
        "/periodos/cerrar",
        json={"empresa_id": test_data["empresa_id"], "periodo": "2026-04"},
        headers=trabajador_headers,
    )
    assert resp.status_code == 403
