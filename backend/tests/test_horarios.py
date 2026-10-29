"""Tests de API de horarios semanales. Sprint 2."""
from datetime import date

from fastapi.testclient import TestClient

from app.models import Empresa, TipoContrato, Trabajador, TurnoPlantilla, Unidad, Usuario


def test_crear_horario_semanal(client: TestClient, db, unique_id):
    """Test de creación de horario semanal."""
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
    
    trabajador = Trabajador(
        codigo=f"W{unique_id}1",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero=f"{unique_id}12345678",
        nombres="Juan",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso=date(2026, 1, 1)
    )
    db.add(trabajador)
    db.flush()
    
    turno = TurnoPlantilla(
        unidad_id=unidad.id,
        nombre="Mañana",
        inicio="08:00",
        fin="16:00",
        refrigerio_min=45
    )
    db.add(turno)
    db.flush()
    
    jefe = Usuario(
        email="jefe@test.com",
        password_hash="hash",
        rol="jefe",
        nombre="Jefe Test",
        unidad_id=unidad.id
    )
    db.add(jefe)
    db.commit()
    
    from app.security import crear_token
    token = crear_token(jefe.id)
    
    resp = client.post(
        "/horarios/",
        json={
            "trabajador_id": trabajador.id,
            "semana_inicio": "2026-11-03",
            "lunes_plantilla_id": turno.id,
            "martes_plantilla_id": turno.id,
            "miercoles_plantilla_id": turno.id,
            "jueves_plantilla_id": turno.id,
            "viernes_plantilla_id": turno.id
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["version"] == 1


def test_horario_alertas_exceso_horas(client: TestClient, db, unique_id):
    """Test de alertas no bloqueantes: >8h/día y >48h/semana."""
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
    
    trabajador = Trabajador(
        codigo=f"W{unique_id}2",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero=f"{unique_id}87654321",
        nombres="Maria",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso=date(2026, 1, 1)
    )
    db.add(trabajador)
    db.flush()
    
    turno_largo = TurnoPlantilla(
        unidad_id=unidad.id,
        nombre="Largo",
        inicio="08:00",
        fin="19:00",
        refrigerio_min=60
    )
    db.add(turno_largo)
    db.flush()
    
    jefe = Usuario(
        email="jefe2@test.com",
        password_hash="hash",
        rol="jefe",
        nombre="Jefe Test",
        unidad_id=unidad.id
    )
    db.add(jefe)
    db.commit()
    
    from app.security import crear_token
    token = crear_token(jefe.id)
    
    resp = client.post(
        "/horarios/",
        json={
            "trabajador_id": trabajador.id,
            "semana_inicio": "2026-11-03",
            "lunes_plantilla_id": turno_largo.id,
            "martes_plantilla_id": turno_largo.id,
            "miercoles_plantilla_id": turno_largo.id,
            "jueves_plantilla_id": turno_largo.id,
            "viernes_plantilla_id": turno_largo.id,
            "sabado_plantilla_id": turno_largo.id
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert "alertas" in data
    assert len(data["alertas"]["warnings"]) > 0


def test_copiar_semana_anterior(client: TestClient, db, unique_id):
    """Test de copiado de horario de semana anterior."""
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
    
    trabajador = Trabajador(
        codigo=f"W{unique_id}3",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero=f"{unique_id}11223344",
        nombres="Pedro",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso=date(2026, 1, 1)
    )
    db.add(trabajador)
    db.flush()
    
    turno = TurnoPlantilla(
        unidad_id=unidad.id,
        nombre="Tarde",
        inicio="14:00",
        fin="22:00",
        refrigerio_min=45
    )
    db.add(turno)
    db.flush()
    
    jefe = Usuario(
        email="jefe3@test.com",
        password_hash="hash",
        rol="jefe",
        nombre="Jefe Test",
        unidad_id=unidad.id
    )
    db.add(jefe)
    db.flush()
    
    from app.models import HorarioPlan
    plan_anterior = HorarioPlan(
        trabajador_id=trabajador.id,
        semana_inicio=date(2026, 10, 28),
        version=1,
        lunes_plantilla_id=turno.id,
        martes_plantilla_id=turno.id,
        miercoles_plantilla_id=turno.id,
        jueves_plantilla_id=turno.id,
        viernes_plantilla_id=turno.id,
        creado_por=jefe.id
    )
    db.add(plan_anterior)
    db.commit()
    
    from app.security import crear_token
    token = crear_token(jefe.id)
    
    resp = client.post(
        f"/horarios/copiar-semana-anterior?trabajador_id={trabajador.id}&semana_inicio=2026-11-04",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 1
