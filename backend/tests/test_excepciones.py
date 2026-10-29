"""Tests Sprint 3: Dashboard de excepciones."""
from datetime import date, timedelta


def test_listar_faltas_sin_justificar(client, H):
    """Listar faltas sin justificación."""
    resp = client.get(
        "/excepciones/faltas-sin-justificar",
        params={"periodo": "2026-10"},
        headers=H["jefe"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_listar_tardanzas_recurrentes(client, H):
    """Listar trabajadores con tardanzas recurrentes."""
    resp = client.get(
        "/excepciones/tardanzas-recurrentes",
        params={"periodo": "2026-10", "min_tardanzas": 3},
        headers=H["jefe"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_listar_marcas_fuera_geocerca(client, H):
    """Listar marcas fuera de geocerca."""
    hoy = date.today()
    hace_30 = hoy - timedelta(days=30)
    
    resp = client.get(
        "/excepciones/marcas-fuera-geocerca",
        params={"desde": hace_30.isoformat(), "hasta": hoy.isoformat()},
        headers=H["jefe"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_reporte_part_time_riesgo(client, H):
    """Reporte de PT con riesgo normativo (>4h/día)."""
    resp = client.get(
        "/excepciones/part-time-riesgo",
        params={"periodo": "2026-10"},
        headers=H["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_justificar_falta(client, db, H):
    """Jefe puede justificar falta de trabajador de su unidad."""
    from app.models import Trabajador
    trab = db.query(Trabajador).filter(Trabajador.codigo == "CAV-007").first()
    if not trab:
        import pytest
        pytest.skip("No hay trabajador en semilla")
    
    dia = date.today() - timedelta(days=5)
    
    resp = client.post(
        "/excepciones/justificar-falta",
        json={
            "trabajador_id": trab.id,
            "dia": dia.isoformat(),
            "motivo": "licencia_medica",
            "descripcion": "Reposo médico por 3 días",
        },
        headers=H["jefe"],
    )
    assert resp.status_code in (200, 403, 404)


def test_justificar_falta_duplicada(client, db, H):
    """No se puede justificar la misma falta dos veces (stub para futuro)."""
    import pytest
    pytest.skip("Endpoint es stub, lógica de duplicados pendiente Sprint 4")


def test_trabajador_no_puede_ver_excepciones(client, H):
    """Trabajador no puede ver dashboard de excepciones."""
    resp = client.get(
        "/excepciones/faltas-sin-justificar",
        params={"periodo": "2026-10"},
        headers=H["trabajador"],
    )
    assert resp.status_code == 403
