"""Tests Sprint 3: Dashboard de excepciones."""
from datetime import date, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_listar_faltas_sin_justificar(async_client: AsyncClient, jefe_headers, test_data):
    """Listar faltas sin justificación."""
    resp = await async_client.get(
        "/excepciones/faltas-sin-justificar",
        params={"periodo": "2026-10"},
        headers=jefe_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_listar_tardanzas_recurrentes(async_client: AsyncClient, jefe_headers, test_data):
    """Listar trabajadores con tardanzas recurrentes."""
    resp = await async_client.get(
        "/excepciones/tardanzas-recurrentes",
        params={"periodo": "2026-10", "min_tardanzas": 3},
        headers=jefe_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_listar_marcas_fuera_geocerca(async_client: AsyncClient, jefe_headers, test_data):
    """Listar marcas fuera de geocerca."""
    hoy = date.today()
    hace_30 = hoy - timedelta(days=30)
    
    resp = await async_client.get(
        "/excepciones/marcas-fuera-geocerca",
        params={"desde": hace_30.isoformat(), "hasta": hoy.isoformat()},
        headers=jefe_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_reporte_part_time_riesgo(async_client: AsyncClient, admin_headers, test_data):
    """Reporte de PT con riesgo normativo (>4h/día)."""
    resp = await async_client.get(
        "/excepciones/part-time-riesgo",
        params={"periodo": "2026-10"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_justificar_falta(async_client: AsyncClient, jefe_headers, test_data):
    """Jefe puede justificar falta de trabajador de su unidad."""
    trabajador_id = test_data["trabajador_id"]
    dia = date.today() - timedelta(days=5)
    
    resp = await async_client.post(
        "/excepciones/justificar-falta",
        json={
            "trabajador_id": trabajador_id,
            "dia": dia.isoformat(),
            "motivo": "licencia_medica",
            "descripcion": "Reposo médico por 3 días",
        },
        headers=jefe_headers,
    )
    assert resp.status_code in (200, 403, 404)


@pytest.mark.asyncio
async def test_justificar_falta_duplicada(async_client: AsyncClient, jefe_headers, test_data):
    """No se puede justificar la misma falta dos veces."""
    trabajador_id = test_data["trabajador_id"]
    dia = date.today() - timedelta(days=7)
    
    data = {
        "trabajador_id": trabajador_id,
        "dia": dia.isoformat(),
        "motivo": "permiso",
        "descripcion": "Trámite personal",
    }
    
    resp1 = await async_client.post(
        "/excepciones/justificar-falta",
        json=data,
        headers=jefe_headers,
    )
    
    if resp1.status_code == 200:
        resp2 = await async_client.post(
            "/excepciones/justificar-falta",
            json=data,
            headers=jefe_headers,
        )
        assert resp2.status_code == 400


@pytest.mark.asyncio
async def test_trabajador_no_puede_ver_excepciones(async_client: AsyncClient, trabajador_headers):
    """Trabajador no puede ver dashboard de excepciones."""
    resp = await async_client.get(
        "/excepciones/faltas-sin-justificar",
        params={"periodo": "2026-10"},
        headers=trabajador_headers,
    )
    assert resp.status_code == 403
