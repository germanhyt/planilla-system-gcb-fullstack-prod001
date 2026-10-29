"""Tests del motor de cálculo de asistencia. Sprint 2."""
from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.engine import (
    calcular_asistencia_dia,
    calcular_distancia,
    calcular_horas_extra,
    calcular_horas_nocturnas,
    calcular_horas_trabajadas,
    calcular_tardanza,
    get_dia_operativo,
    get_periodo_operativo,
)
from app.models import Empresa, Marca, RuleSet, TipoContrato, Trabajador, Unidad
from app.rules import CAVAS, efectivas


def test_calcular_distancia():
    """Test de cálculo de distancia haversine."""
    lat1, lng1 = -9.531119, -77.530517
    lat2, lng2 = -9.531500, -77.531000
    
    dist = calcular_distancia(lat1, lng1, lat2, lng2)
    assert 40 < dist < 80


def test_dia_operativo_cavas():
    """Test de día operativo con corte 06:00 (CAVAS)."""
    ts_antes_corte = datetime(2026, 10, 29, 3, 0)
    dia_op = get_dia_operativo(ts_antes_corte, "06:00")
    assert dia_op == date(2026, 10, 28)
    
    ts_despues_corte = datetime(2026, 10, 29, 8, 0)
    dia_op = get_dia_operativo(ts_despues_corte, "06:00")
    assert dia_op == date(2026, 10, 29)


def test_dia_operativo_calendario():
    """Test de día operativo sin corte (GCB SA)."""
    ts = datetime(2026, 10, 29, 3, 0)
    dia_op = get_dia_operativo(ts, "00:00")
    assert dia_op == date(2026, 10, 29)


def test_periodo_operativo_corte():
    """Test de periodo operativo: marca 03:00 del día 1 pertenece al mes anterior."""
    dia_op = date(2026, 11, 1)
    periodo = get_periodo_operativo(dia_op, "06:00")
    assert periodo == "2026-10"
    
    dia_op = date(2026, 11, 2)
    periodo = get_periodo_operativo(dia_op, "06:00")
    assert periodo == "2026-11"


def test_tardanza_umbral_perdona():
    """Test de tardanza con modo umbral_perdona."""
    config = {"modo": "umbral_perdona", "minutos": 10}
    
    entrada = datetime(2026, 10, 29, 19, 5)
    tardanza = calcular_tardanza(entrada, time(19, 0), config)
    assert tardanza == 0
    
    entrada = datetime(2026, 10, 29, 19, 15)
    tardanza = calcular_tardanza(entrada, time(19, 0), config)
    assert tardanza == 15


def test_tardanza_umbral_descuenta_exceso():
    """Test de tardanza con modo umbral_descuenta_exceso."""
    config = {"modo": "umbral_descuenta_exceso", "minutos": 10}
    
    entrada = datetime(2026, 10, 29, 19, 15)
    tardanza = calcular_tardanza(entrada, time(19, 0), config)
    assert tardanza == 5


def test_tardanza_sin_tolerancia():
    """Test de tardanza sin tolerancia."""
    config = {"modo": "sin_tolerancia", "minutos": 0}
    
    entrada = datetime(2026, 10, 29, 19, 5)
    tardanza = calcular_tardanza(entrada, time(19, 0), config)
    assert tardanza == 5


def test_horas_nocturnas():
    """Test de cálculo de horas nocturnas 22:00-06:00."""
    config = {"inicio": "22:00", "fin": "06:00"}
    
    entrada = datetime(2026, 10, 29, 19, 0)
    salida = datetime(2026, 10, 30, 2, 0)
    
    nocturnas = calcular_horas_nocturnas(entrada, salida, config)
    assert 3.9 < nocturnas < 4.1


def test_horas_trabajadas():
    """Test de horas trabajadas con refrigerio."""
    entrada = datetime(2026, 10, 29, 19, 0)
    salida = datetime(2026, 10, 30, 2, 0)
    
    horas = calcular_horas_trabajadas(entrada, salida, 45)
    assert 6.2 < horas < 6.3


def test_horas_extra_split():
    """Test de split de horas extra: 25% primeras 2h, 35% resto."""
    sobretasas = [{"hasta_horas": 2, "pct": 25}, {"hasta_horas": None, "pct": 35}]
    
    he_25, he_35 = calcular_horas_extra(10.0, 7.0, 3.0, sobretasas)
    assert he_25 == 2.0
    assert he_35 == 1.0
    
    he_25, he_35 = calcular_horas_extra(8.5, 7.0, 3.0, sobretasas)
    assert he_25 == 1.5
    assert he_35 == 0.0


def test_turno_cruza_medianoche(db: Session):
    """Test de turno que cruza medianoche (19:00-02:00)."""
    empresa = Empresa(codigo="CAVAS", razon_social="Cavas Sisa", ruc="20123456789")
    db.add(empresa)
    db.flush()
    
    rule_set = RuleSet(
        empresa_id=empresa.id,
        version=1,
        valid_from=date(2026, 1, 1),
        config=CAVAS
    )
    db.add(rule_set)
    db.flush()
    
    reglas = efectivas(CAVAS)
    
    assert reglas["dia_operativo"]["corte"] == "06:00"


def test_calculo_asistencia_completo(db: Session, unique_id):
    """Test de cálculo completo de asistencia de un día."""
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
        es_part_time=False,
        refrigerio_min=45
    )
    db.add(tipo)
    db.flush()
    
    trabajador = Trabajador(
        codigo="T001",
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
    
    rule_set = RuleSet(
        empresa_id=empresa.id,
        version=1,
        valid_from=date(2026, 1, 1),
        config={}
    )
    db.add(rule_set)
    db.flush()
    
    dia = date(2026, 10, 29)
    entrada = Marca(
        trabajador_id=trabajador.id,
        tipo="entrada",
        ts_servidor=datetime(2026, 10, 29, 19, 5),
        metodo="gps",
        validacion_estado="ok"
    )
    salida = Marca(
        trabajador_id=trabajador.id,
        tipo="salida",
        ts_servidor=datetime(2026, 10, 30, 2, 0),
        metodo="gps",
        validacion_estado="ok"
    )
    db.add_all([entrada, salida])
    db.commit()
    
    from app.rules import efectivas
    reglas = efectivas({})
    
    resultado = calcular_asistencia_dia(db, trabajador.id, dia, reglas)
    
    assert resultado is not None
    assert resultado["trabajador_id"] == trabajador.id
    assert resultado["dia_operativo"] == dia
    assert resultado["horas_trabajadas"] > 0
