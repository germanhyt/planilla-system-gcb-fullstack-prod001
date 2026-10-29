"""Tests de API de regularización de HE. Sprint 2."""
from datetime import date

from fastapi.testclient import TestClient

from app.models import Asistencia, Empresa, RegularizacionHE, RuleSet, Trabajador, TipoContrato, Unidad, Usuario


def test_listar_pendientes(client: TestClient, db):
    """Test de listado de regularizaciones pendientes."""
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
    
    trabajador = Trabajador(
        codigo="T001",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero="12345678",
        nombres="Juan",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso=date(2026, 1, 1)
    )
    db.add(trabajador)
    db.flush()
    
    rule_set = RuleSet(
        empresa_id=empresa.id,
        version=1,
        valid_from=date(2026, 1, 1),
        config={}
    )
    db.add(rule_set)
    db.flush()
    
    asistencia = Asistencia(
        trabajador_id=trabajador.id,
        dia_operativo=date(2026, 10, 29),
        periodo="2026-10",
        horas_programadas=7.0,
        horas_trabajadas=9.5,
        tardanza_min=0,
        horas_extra_25=0,
        horas_extra_35=0,
        horas_nocturnas=0,
        exceso_no_programado=2.5,
        rule_set_id=rule_set.id,
        periodo_cerrado=False
    )
    db.add(asistencia)
    db.flush()
    
    reg = RegularizacionHE(
        asistencia_id=asistencia.id,
        trabajador_id=trabajador.id,
        horas_exceso=2.5,
        estado="pendiente"
    )
    db.add(reg)
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
    
    resp = client.get(
        "/regularizaciones/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert data[0]["estado"] == "pendiente"
    assert data[0]["horas_exceso"] == 2.5


def test_aprobar_regularizacion(client: TestClient, db):
    """Test de aprobación de regularización."""
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
    
    trabajador = Trabajador(
        codigo="T002",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero="87654321",
        nombres="Maria",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso=date(2026, 1, 1)
    )
    db.add(trabajador)
    db.flush()
    
    rule_set = RuleSet(
        empresa_id=empresa.id,
        version=1,
        valid_from=date(2026, 1, 1),
        config={}
    )
    db.add(rule_set)
    db.flush()
    
    asistencia = Asistencia(
        trabajador_id=trabajador.id,
        dia_operativo=date(2026, 10, 29),
        periodo="2026-10",
        horas_programadas=7.0,
        horas_trabajadas=9.0,
        tardanza_min=0,
        horas_extra_25=0,
        horas_extra_35=0,
        horas_nocturnas=0,
        exceso_no_programado=2.0,
        rule_set_id=rule_set.id,
        periodo_cerrado=False
    )
    db.add(asistencia)
    db.flush()
    
    reg = RegularizacionHE(
        asistencia_id=asistencia.id,
        trabajador_id=trabajador.id,
        horas_exceso=2.0,
        estado="pendiente"
    )
    db.add(reg)
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
        f"/regularizaciones/{reg.id}/decidir",
        json={
            "aprobar": True,
            "destino": "pago",
            "observacion": "Aprobado por emergencia"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["estado"] == "aprobado"
    assert data["destino"] == "pago"


def test_rechazar_regularizacion(client: TestClient, db):
    """Test de rechazo de regularización."""
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
    
    trabajador = Trabajador(
        codigo="T003",
        empresa_id=empresa.id,
        unidad_id=unidad.id,
        doc_tipo="DNI",
        doc_numero="11223344",
        nombres="Pedro",
        apellidos="Test",
        tipo_contrato_id=tipo.id,
        fecha_ingreso=date(2026, 1, 1)
    )
    db.add(trabajador)
    db.flush()
    
    rule_set = RuleSet(
        empresa_id=empresa.id,
        version=1,
        valid_from=date(2026, 1, 1),
        config={}
    )
    db.add(rule_set)
    db.flush()
    
    asistencia = Asistencia(
        trabajador_id=trabajador.id,
        dia_operativo=date(2026, 10, 29),
        periodo="2026-10",
        horas_programadas=7.0,
        horas_trabajadas=8.5,
        tardanza_min=0,
        horas_extra_25=0,
        horas_extra_35=0,
        horas_nocturnas=0,
        exceso_no_programado=1.5,
        rule_set_id=rule_set.id,
        periodo_cerrado=False
    )
    db.add(asistencia)
    db.flush()
    
    reg = RegularizacionHE(
        asistencia_id=asistencia.id,
        trabajador_id=trabajador.id,
        horas_exceso=1.5,
        estado="pendiente"
    )
    db.add(reg)
    db.flush()
    
    jefe = Usuario(
        email="jefe3@test.com",
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
        f"/regularizaciones/{reg.id}/decidir",
        json={
            "aprobar": False,
            "observacion": "No justificado"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["estado"] == "rechazado"
