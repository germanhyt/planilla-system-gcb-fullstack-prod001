"""Tests de API de marcas (check-in/out). Sprint 2."""
from fastapi.testclient import TestClient

from app.models import Empresa, Sede, TipoContrato, Trabajador, Unidad, Usuario


def test_registrar_marca_gps(client: TestClient, db, admin_token):
    """Test de registro de marca con GPS."""
    empresa = Empresa(codigo="TST", razon_social="Test", ruc="20111111111")
    db.add(empresa)
    db.flush()
    
    unidad = Unidad(empresa_id=empresa.id, codigo="U1", nombre="Unidad 1")
    db.add(unidad)
    db.flush()
    
    sede = Sede(
        unidad_id=unidad.id,
        nombre="Sede Principal",
        direccion="Test",
        lat=-9.531119,
        lng=-77.530517,
        radio_geocerca_m=100
    )
    db.add(sede)
    db.flush()
    
    tipo = TipoContrato(
        codigo="FT",
        nombre="Full Time",
        horas_mes=208,
        jornada_diaria_min=480,
        es_part_time=False
    )
    db.add(tipo)
    db.flush()
    
    usuario = Usuario(
        email="trabajador@test.com",
        password_hash="hash",
        rol="trabajador",
        nombre="Test Worker"
    )
    db.add(usuario)
    db.flush()
    
    trabajador = Trabajador(
        codigo="T001",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        sede_id=sede.id,
        doc_tipo="DNI",
        doc_numero="12345678",
        nombres="Juan",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso="2026-01-01",
        usuario_id=usuario.id
    )
    db.add(trabajador)
    db.commit()
    
    from app.security import crear_token
    token = crear_token(usuario.id)
    
    resp = client.post(
        "/marcas/",
        json={
            "tipo": "entrada",
            "lat": -9.531150,
            "lng": -77.530550
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["validacion_estado"] == "ok"
    assert data["distancia_m"] < 100


def test_registrar_marca_fuera_geocerca(client: TestClient, db):
    """Test de marca fuera de la geocerca."""
    empresa = Empresa(codigo="TST", razon_social="Test", ruc="20111111111")
    db.add(empresa)
    db.flush()
    
    unidad = Unidad(empresa_id=empresa.id, codigo="U1", nombre="Unidad 1")
    db.add(unidad)
    db.flush()
    
    sede = Sede(
        unidad_id=unidad.id,
        nombre="Sede Principal",
        direccion="Test",
        lat=-9.531119,
        lng=-77.530517,
        radio_geocerca_m=50
    )
    db.add(sede)
    db.flush()
    
    tipo = TipoContrato(
        codigo="FT",
        nombre="Full Time",
        horas_mes=208,
        jornada_diaria_min=480,
        es_part_time=False
    )
    db.add(tipo)
    db.flush()
    
    usuario = Usuario(
        email="trabajador2@test.com",
        password_hash="hash",
        rol="trabajador",
        nombre="Test Worker"
    )
    db.add(usuario)
    db.flush()
    
    trabajador = Trabajador(
        codigo="T002",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        sede_id=sede.id,
        doc_tipo="DNI",
        doc_numero="87654321",
        nombres="Maria",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso="2026-01-01",
        usuario_id=usuario.id
    )
    db.add(trabajador)
    db.commit()
    
    from app.security import crear_token
    token = crear_token(usuario.id)
    
    resp = client.post(
        "/marcas/",
        json={
            "tipo": "entrada",
            "lat": -9.532000,
            "lng": -77.531500
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["validacion_estado"] == "fuera_geocerca"
    assert data["distancia_m"] > 50


def test_registrar_marca_duplicada(client: TestClient, db):
    """Test de rechazo de marca duplicada en ventana de 5 min."""
    empresa = Empresa(codigo="TST", razon_social="Test", ruc="20111111111")
    db.add(empresa)
    db.flush()
    
    unidad = Unidad(empresa_id=empresa.id, codigo="U1", nombre="Unidad 1")
    db.add(unidad)
    db.flush()
    
    tipo = TipoContrato(
        codigo="FT",
        nombre="Full Time",
        horas_mes=208,
        jornada_diaria_min=480,
        es_part_time=False
    )
    db.add(tipo)
    db.flush()
    
    usuario = Usuario(
        email="trabajador3@test.com",
        password_hash="hash",
        rol="trabajador",
        nombre="Test Worker"
    )
    db.add(usuario)
    db.flush()
    
    trabajador = Trabajador(
        codigo="T003",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero="11223344",
        nombres="Pedro",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso="2026-01-01",
        usuario_id=usuario.id
    )
    db.add(trabajador)
    db.commit()
    
    from app.security import crear_token
    token = crear_token(usuario.id)
    
    resp1 = client.post(
        "/marcas/",
        json={"tipo": "entrada"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp1.status_code == 200
    
    resp2 = client.post(
        "/marcas/",
        json={"tipo": "entrada"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp2.status_code == 400
    assert "duplicado" in resp2.json()["detail"].lower()


def test_registrar_marca_manual_jefe(client: TestClient, db):
    """Test de marca manual por jefe."""
    empresa = Empresa(codigo="TST", razon_social="Test", ruc="20111111111")
    db.add(empresa)
    db.flush()
    
    unidad = Unidad(empresa_id=empresa.id, codigo="U1", nombre="Unidad 1")
    db.add(unidad)
    db.flush()
    
    tipo = TipoContrato(
        codigo="FT",
        nombre="Full Time",
        horas_mes=208,
        jornada_diaria_min=480,
        es_part_time=False
    )
    db.add(tipo)
    db.flush()
    
    jefe = Usuario(
        email="jefe@test.com",
        password_hash="hash",
        rol="jefe",
        nombre="Jefe Test",
        unidad_id=unidad.id
    )
    db.add(jefe)
    db.flush()
    
    trabajador = Trabajador(
        codigo="T004",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero="55667788",
        nombres="Ana",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso="2026-01-01"
    )
    db.add(trabajador)
    db.commit()
    
    from app.security import crear_token
    token = crear_token(jefe.id)
    
    resp = client.post(
        "/marcas/manual",
        json={
            "trabajador_id": trabajador.id,
            "tipo": "entrada",
            "ts_servidor": "2026-10-29T19:00:00",
            "razon_manual": "Olvido marcar en sistema"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
