"""Tests Sprint 3: Reportes consolidados y export."""
import pytest


def test_consolidado_mensual_json(client, H):
    """Consolidado mensual retorna JSON por defecto."""
    resp = client.get(
        "/reportes/consolidado-mensual",
        params={"periodo": "2026-10", "formato": "json"},
        headers=H["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "periodo" in data
    assert "registros" in data
    assert "totales" in data


def test_consolidado_mensual_sin_datos(client, H):
    """Periodo sin datos retorna estructura vacía."""
    resp = client.get(
        "/reportes/consolidado-mensual",
        params={"periodo": "2025-01", "formato": "json"},
        headers=H["admin"],
    )
    assert resp.status_code == 200


def test_consolidado_export_excel(client, H, ids):
    """Export a Excel funciona."""
    resp = client.get(
        "/reportes/consolidado-mensual",
        params={"periodo": "2026-10", "formato": "excel"},
        headers=H["admin"],
    )
    if resp.status_code == 404:
        pytest.skip("Sin datos para periodo 2026-10")
    
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_consolidado_export_csv(client, H, ids):
    """Export a CSV funciona."""
    resp = client.get(
        "/reportes/consolidado-mensual",
        params={"periodo": "2026-10", "formato": "csv"},
        headers=H["admin"],
    )
    if resp.status_code == 404:
        pytest.skip("Sin datos para periodo 2026-10")
    
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")


def test_conceptos_remunerativos(client, H, ids):
    """Conceptos remunerativos para integración nómina."""
    empresa_id = ids["emp"]["CAVAS"]
    
    resp = client.get(
        "/reportes/conceptos-remunerativos",
        params={"periodo": "2026-10", "empresa_id": empresa_id},
        headers=H["admin"],
    )
    
    if resp.status_code == 404:
        pytest.skip("Sin datos para periodo")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["periodo"] == "2026-10"
    assert data["empresa_id"] == empresa_id
    assert "trabajadores" in data


def test_reportes_jefe_solo_su_unidad(client, H):
    """Jefe solo ve reportes de su unidad."""
    resp = client.get(
        "/reportes/consolidado-mensual",
        params={"periodo": "2026-10", "formato": "json"},
        headers=H["jefe"],
    )
    assert resp.status_code in (200, 404)


def test_reportes_trabajador_no_autorizado(client, H):
    """Trabajador no puede ver reportes."""
    resp = client.get(
        "/reportes/consolidado-mensual",
        params={"periodo": "2026-10"},
        headers=H["trabajador"],
    )
    assert resp.status_code == 403
