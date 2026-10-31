"""Tests Sprint 3: Cierre de periodos."""


def test_cerrar_periodo(client, H, ids):
    """Admin puede cerrar periodo."""
    empresa_id = ids["emp"]["CAVAS"]
    
    resp = client.post(
        "/periodos/cerrar",
        json={"empresa_id": empresa_id, "periodo": "2026-09", "confirmar": True},
        headers=H["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["periodo"] == "2026-09"
    assert data["estado"] == "cerrado"


def test_cerrar_periodo_duplicado(client, H, ids):
    """No se puede cerrar el mismo periodo dos veces."""
    empresa_id = ids["emp"]["CAVAS"]
    
    client.post(
        "/periodos/cerrar",
        json={"empresa_id": empresa_id, "periodo": "2026-08", "confirmar": True},
        headers=H["admin"],
    )
    
    resp = client.post(
        "/periodos/cerrar",
        json={"empresa_id": empresa_id, "periodo": "2026-08", "confirmar": True},
        headers=H["admin"],
    )
    assert resp.status_code == 400


def test_reabrir_periodo_admin(client, H, ids):
    """Admin puede reabrir periodo con razón."""
    empresa_id = ids["emp"]["CAVAS"]
    
    cierre_resp = client.post(
        "/periodos/cerrar",
        json={"empresa_id": empresa_id, "periodo": "2026-07", "confirmar": True},
        headers=H["admin"],
    )
    assert cierre_resp.status_code == 200, cierre_resp.text
    cierre_id = cierre_resp.json()["id"]
    
    resp = client.post(
        f"/periodos/reabrir/{cierre_id}",
        json={"razon_reapertura": "Corrección de errores en marcas del periodo"},
        headers=H["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["estado"] == "reabierto"


def test_reabrir_periodo_rrhh_no_autorizado(client, H, ids):
    """RRHH no puede reabrir (solo admin)."""
    empresa_id = ids["emp"]["CAVAS"]
    
    cierre_resp = client.post(
        "/periodos/cerrar",
        json={"empresa_id": empresa_id, "periodo": "2026-06", "confirmar": True},
        headers=H["rrhh"],
    )
    assert cierre_resp.status_code == 200, cierre_resp.text
    cierre_id = cierre_resp.json()["id"]
    
    resp = client.post(
        f"/periodos/reabrir/{cierre_id}",
        json={"razon_reapertura": "Intento de reapertura"},
        headers=H["rrhh"],
    )
    assert resp.status_code == 403


def test_historial_cierres(client, H, ids):
    """Listar histórico de cierres."""
    empresa_id = ids["emp"]["CAVAS"]
    
    client.post(
        "/periodos/cerrar",
        json={"empresa_id": empresa_id, "periodo": "2026-05", "confirmar": True},
        headers=H["admin"],
    )
    
    resp = client.get(
        "/periodos/historial",
        params={"empresa_id": empresa_id},
        headers=H["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "periodo" in data[0]
        assert "estado" in data[0]


def test_trabajador_no_puede_cerrar(client, H, ids):
    """Trabajador no puede cerrar periodos."""
    resp = client.post(
        "/periodos/cerrar",
        json={"empresa_id": ids["emp"]["CAVAS"], "periodo": "2026-04", "confirmar": True},
        headers=H["trabajador"],
    )
    assert resp.status_code == 403
