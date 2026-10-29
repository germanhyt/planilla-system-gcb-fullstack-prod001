"""Tests de API de marcas (check-in/out). Sprint 2."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.models import Empresa, Marca, Sede, TipoContrato, Trabajador, Unidad, Usuario


def test_registrar_marca_gps(client: TestClient, db, H, unique_id):
    """Test de registro de marca con GPS."""
    empresa = Empresa(codigo=unique_id, razon_social=f"Test{unique_id}", ruc=f"20{unique_id[1:]}111")
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
        codigo=f"FT{unique_id}",
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
        codigo=f"W{unique_id}1",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        sede_id=sede.id,
        doc_tipo="DNI",
        doc_numero=f"{unique_id}12345678",
        nombres="Juan",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso="2026-01-01",
        usuario_id=usuario.id
    )
    db.add(trabajador)
    db.commit()
    
    from app.security import create_token
    token = create_token(usuario.id, usuario.rol)
    
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


def test_registrar_marca_fuera_geocerca(client: TestClient, db, unique_id):
    """Test de marca fuera de la geocerca."""
    empresa = Empresa(codigo=unique_id, razon_social=f"Test{unique_id}", ruc=f"20{unique_id[1:]}111")
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
        codigo=f"FT{unique_id}",
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
        codigo=f"W{unique_id}2",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        sede_id=sede.id,
        doc_tipo="DNI",
        doc_numero=f"{unique_id}87654321",
        nombres="Maria",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso="2026-01-01",
        usuario_id=usuario.id
    )
    db.add(trabajador)
    db.commit()
    
    from app.security import create_token
    token = create_token(usuario.id, usuario.rol)
    
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


def test_registrar_marca_duplicada(client: TestClient, db, unique_id):
    """Test de rechazo de marca duplicada en ventana de 5 min."""
    empresa = Empresa(codigo=unique_id, razon_social=f"Test{unique_id}", ruc=f"20{unique_id[1:]}111")
    db.add(empresa)
    db.flush()
    
    unidad = Unidad(empresa_id=empresa.id, codigo="U1", nombre="Unidad 1")
    db.add(unidad)
    db.flush()
    
    tipo = TipoContrato(
        codigo=f"FT{unique_id}",
        nombre="Full Time",
        horas_mes=208,
        jornada_diaria_min=480,
        es_part_time=False
    )
    db.add(tipo)
    db.flush()
    
    usuario = Usuario(
        email=f"{unique_id}trabajador3@test.com",
        password_hash="hash",
        rol="trabajador",
        nombre="Test Worker"
    )
    db.add(usuario)
    db.flush()
    
    trabajador = Trabajador(
        codigo=f"W{unique_id}3",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero=f"{unique_id}11223344",
        nombres="Pedro",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso="2026-01-01",
        usuario_id=usuario.id
    )
    db.add(trabajador)
    db.commit()
    
    from app.security import create_token
    token = create_token(usuario.id, usuario.rol)
    
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
    detail = resp2.json()["detail"].lower()
    assert "duplicado" in detail or "ya existe" in detail or "últimos 5 minutos" in detail


def test_registrar_marca_payload_correcto(client: TestClient, db, unique_id):
    """Regression test: verify correct JSON payload shape is accepted (not double-encoded)."""
    empresa = Empresa(codigo=unique_id, razon_social=f"Test{unique_id}", ruc=f"20{unique_id[1:]}111")
    db.add(empresa)
    db.flush()
    
    unidad = Unidad(empresa_id=empresa.id, codigo="U1", nombre="Unidad 1")
    db.add(unidad)
    db.flush()
    
    tipo = TipoContrato(
        codigo=f"FT{unique_id}",
        nombre="Full Time",
        horas_mes=208,
        jornada_diaria_min=480,
        es_part_time=False
    )
    db.add(tipo)
    db.flush()
    
    usuario = Usuario(
        email=f"{unique_id}test@test.com",
        password_hash="hash",
        rol="trabajador",
        nombre="Test Worker"
    )
    db.add(usuario)
    db.flush()
    
    trabajador = Trabajador(
        codigo=f"W{unique_id}5",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero=f"{unique_id}99887766",
        nombres="Carlos",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso="2026-01-01",
        usuario_id=usuario.id
    )
    db.add(trabajador)
    db.commit()
    
    from app.security import create_token
    token = create_token(usuario.id, usuario.rol)
    
    resp_correct = client.post(
        "/marcas/",
        json={"tipo": "entrada", "lat": -9.531119, "lng": -77.530517},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_correct.status_code == 200, f"Correct payload should be accepted: {resp_correct.json()}"
    
    import json
    double_encoded = json.dumps({"tipo": "salida", "lat": -9.531119, "lng": -77.530517})
    resp_double = client.post(
        "/marcas/",
        json=double_encoded,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_double.status_code == 422, "Double-encoded payload should be rejected"


def test_registrar_marca_manual_jefe(client: TestClient, db, unique_id):
    """Test de marca manual por jefe."""
    empresa = Empresa(codigo=unique_id, razon_social=f"Test{unique_id}", ruc=f"20{unique_id[1:]}111")
    db.add(empresa)
    db.flush()
    
    unidad = Unidad(empresa_id=empresa.id, codigo="U1", nombre="Unidad 1")
    db.add(unidad)
    db.flush()
    
    tipo = TipoContrato(
        codigo=f"FT{unique_id}",
        nombre="Full Time",
        horas_mes=208,
        jornada_diaria_min=480,
        es_part_time=False
    )
    db.add(tipo)
    db.flush()
    
    jefe = Usuario(
        email=f"{unique_id}jefe@test.com",
        password_hash="hash",
        rol="jefe",
        nombre="Jefe Test",
        unidad_id=unidad.id
    )
    db.add(jefe)
    db.flush()
    
    trabajador = Trabajador(
        codigo=f"W{unique_id}4",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero=f"{unique_id}55667788",
        nombres="Ana",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso="2026-01-01"
    )
    db.add(trabajador)
    db.commit()
    
    from app.security import create_token
    token = create_token(jefe.id, jefe.rol)
    
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


def test_ts_servidor_timezone_aware(client: TestClient, db, unique_id):
    """Regression test: ts_servidor must be timezone-aware UTC, not naive datetime."""
    empresa = Empresa(codigo=unique_id, razon_social=f"Test{unique_id}", ruc=f"20{unique_id[1:]}111")
    db.add(empresa)
    db.flush()
    
    unidad = Unidad(empresa_id=empresa.id, codigo="U1", nombre="Unidad 1")
    db.add(unidad)
    db.flush()
    
    tipo = TipoContrato(
        codigo=f"FT{unique_id}",
        nombre="Full Time",
        horas_mes=208,
        jornada_diaria_min=480,
        es_part_time=False
    )
    db.add(tipo)
    db.flush()
    
    usuario = Usuario(
        email=f"{unique_id}tz@test.com",
        password_hash="hash",
        rol="trabajador",
        nombre="TZ Test"
    )
    db.add(usuario)
    db.flush()
    
    trabajador = Trabajador(
        codigo=f"W{unique_id}6",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero=f"{unique_id}12121212",
        nombres="Test",
        apellidos="TZ",
        tipo_contrato_id=tipo.id,
        fecha_ingreso="2026-01-01",
        usuario_id=usuario.id
    )
    db.add(trabajador)
    db.commit()
    
    from app.security import create_token
    token = create_token(usuario.id, usuario.rol)
    
    before = datetime.now(timezone.utc)
    
    resp = client.post(
        "/marcas/",
        json={
            "tipo": "entrada",
            "lat": -9.531119,
            "lng": -77.530517,
            "ts_cliente": "2026-10-29T16:40:13-05:00"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    after = datetime.now(timezone.utc)
    
    assert resp.status_code == 200
    marca_id = resp.json()["id"]
    
    marca = db.query(Marca).get(marca_id)
    assert marca is not None
    assert marca.ts_servidor.tzinfo is not None, "ts_servidor must be timezone-aware"
    
    delta_before = (marca.ts_servidor - before).total_seconds()
    delta_after = (after - marca.ts_servidor).total_seconds()
    
    assert delta_before >= -1, f"ts_servidor {marca.ts_servidor} is {abs(delta_before)}s before test start {before}"
    assert delta_after >= -1, f"ts_servidor {marca.ts_servidor} is {abs(delta_after)}s after test end {after}"
    assert abs(delta_before) < 10, f"ts_servidor {marca.ts_servidor} too far from real time (start {before})"


def test_marca_16h40_lima_operational_day(client: TestClient, db, unique_id):
    """Regression test: mark at 16:40 Lima time must land on correct operational day (not shifted +5h)."""
    empresa = Empresa(codigo=unique_id, razon_social=f"Test{unique_id}", ruc=f"20{unique_id[1:]}111")
    db.add(empresa)
    db.flush()
    
    unidad = Unidad(empresa_id=empresa.id, codigo="U1", nombre="Unidad 1")
    db.add(unidad)
    db.flush()
    
    tipo = TipoContrato(
        codigo=f"FT{unique_id}",
        nombre="Full Time",
        horas_mes=208,
        jornada_diaria_min=480,
        es_part_time=False
    )
    db.add(tipo)
    db.flush()
    
    usuario = Usuario(
        email=f"{unique_id}opday@test.com",
        password_hash="hash",
        rol="trabajador",
        nombre="OpDay Test"
    )
    db.add(usuario)
    db.flush()
    
    trabajador = Trabajador(
        codigo=f"W{unique_id}7",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero=f"{unique_id}34343434",
        nombres="Test",
        apellidos="OpDay",
        tipo_contrato_id=tipo.id,
        fecha_ingreso="2026-01-01",
        usuario_id=usuario.id
    )
    db.add(trabajador)
    db.commit()
    
    from app.security import create_token
    token = create_token(usuario.id, usuario.rol)
    
    resp = client.post(
        "/marcas/",
        json={
            "tipo": "entrada",
            "lat": -9.531119,
            "lng": -77.530517,
            "ts_cliente": "2026-10-29T16:40:13-05:00"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert resp.status_code == 200
    marca_id = resp.json()["id"]
    
    marca = db.query(Marca).get(marca_id)
    assert marca is not None
    
    ts_utc = marca.ts_servidor.astimezone(timezone.utc)
    hour_utc = ts_utc.hour
    
    assert 20 <= hour_utc <= 23, (
        f"Mark at ~16:40 Lima (21:40 UTC) stored as {marca.ts_servidor}. "
        f"Expected hour 21-23 UTC but got {hour_utc} UTC. "
        f"This indicates naive datetime.utcnow() was written into timestamptz column."
    )
