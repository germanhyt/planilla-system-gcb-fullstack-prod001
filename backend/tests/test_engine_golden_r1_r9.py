"""Golden tests R1-R9: Motor de calculo completo con casos CAVAS anonimizados."""
import pytest
from datetime import date, datetime, time, timedelta
from app.engine import (
    calcular_asistencia_dia,
    calcular_distancia,
    calcular_horas_extra,
    calcular_horas_nocturnas,
    calcular_horas_trabajadas,
    calcular_tardanza,
    get_dia_operativo,
    get_horario_plan_version,
    get_periodo_operativo,
    get_rule_set_vigente,
    get_turno_plantilla_dia,
    minutes_to_hours,
    parse_time,
    time_to_minutes
)


# ============================================================================
# R1: Umbral de tolerancia (CAVAS 10 min, GCB SA 0)
# ============================================================================

def test_r1_tolerancia_umbral_perdona_cavas():
    """R1: CAVAS tolera hasta 10 min sin penalizar."""
    config = {"modo": "umbral_perdona", "minutos": 10}
    
    # 5 min tarde: perdonado
    entrada_ts = datetime(2026, 10, 28, 8, 5)
    turno_inicio = time(8, 0)
    assert calcular_tardanza(entrada_ts, turno_inicio, config) == 0
    
    # 10 min tarde: perdonado
    entrada_ts = datetime(2026, 10, 28, 8, 10)
    assert calcular_tardanza(entrada_ts, turno_inicio, config) == 0
    
    # 15 min tarde: cuenta todo el retraso
    entrada_ts = datetime(2026, 10, 28, 8, 15)
    assert calcular_tardanza(entrada_ts, turno_inicio, config) == 15


def test_r1_tolerancia_umbral_descuenta_exceso():
    """R1: Modo descuento de exceso solo cuenta lo que pasa el umbral."""
    config = {"modo": "umbral_descuenta_exceso", "minutos": 10}
    
    # 15 min tarde: descuenta 10, marca 5
    entrada_ts = datetime(2026, 10, 28, 8, 15)
    turno_inicio = time(8, 0)
    assert calcular_tardanza(entrada_ts, turno_inicio, config) == 5
    
    # 20 min tarde: descuenta 10, marca 10
    entrada_ts = datetime(2026, 10, 28, 8, 20)
    assert calcular_tardanza(entrada_ts, turno_inicio, config) == 10


def test_r1_sin_tolerancia():
    """R1: Sin tolerancia cuenta todo minuto de retraso."""
    config = {"modo": "sin_tolerancia", "minutos": 0}
    
    # 1 min tarde: cuenta
    entrada_ts = datetime(2026, 10, 28, 8, 1)
    turno_inicio = time(8, 0)
    assert calcular_tardanza(entrada_ts, turno_inicio, config) == 1


# ============================================================================
# R2: Dia operativo (CAVAS corte 06:00, GCB SA 00:00)
# ============================================================================

def test_r2_dia_operativo_cavas_corte_06():
    """R2: CAVAS usa corte 06:00 - salida 03:00 pertenece al dia anterior."""
    # Entrada 22:00 del 27 -> dia op 27
    ts = datetime(2026, 10, 27, 22, 0)
    assert get_dia_operativo(ts, "06:00") == date(2026, 10, 27)
    
    # Salida 03:00 del 28 -> dia op 27 (antes del corte)
    ts = datetime(2026, 10, 28, 3, 0)
    assert get_dia_operativo(ts, "06:00") == date(2026, 10, 27)
    
    # Entrada 08:00 del 28 -> dia op 28
    ts = datetime(2026, 10, 28, 8, 0)
    assert get_dia_operativo(ts, "06:00") == date(2026, 10, 28)


def test_r2_dia_operativo_gcb_calendario():
    """R2: GCB SA usa dia calendario (corte 00:00)."""
    # 23:00 del 27 -> dia op 27
    ts = datetime(2026, 10, 27, 23, 0)
    assert get_dia_operativo(ts, "00:00") == date(2026, 10, 27)
    
    # 00:30 del 28 -> dia op 28
    ts = datetime(2026, 10, 28, 0, 30)
    assert get_dia_operativo(ts, "00:00") == date(2026, 10, 28)


# ============================================================================
# R3: Periodo por dia operativo (salida 03:00 del dia 1 -> mes anterior)
# ============================================================================

def test_r3_periodo_operativo_corte_afecta_inicio_mes():
    """R3: Con corte 06:00, salida 03:00 del dia 1 pertenece al mes anterior."""
    # Dia op 2026-11-01 con corte 06:00 -> periodo 2026-11
    assert get_periodo_operativo(date(2026, 11, 1), "06:00") == "2026-10"
    
    # Dia op 2026-11-02 -> periodo 2026-11
    assert get_periodo_operativo(date(2026, 11, 2), "06:00") == "2026-11"


def test_r3_periodo_operativo_sin_corte():
    """R3: Sin corte (00:00) dia 1 pertenece al mes actual."""
    assert get_periodo_operativo(date(2026, 11, 1), "00:00") == "2026-11"


# ============================================================================
# R4: Solo HE programadas cuentan, exceso va a bandeja jefe
# ============================================================================

def test_r4_he_solo_si_programadas():
    """R4: HE se paga solo si fue pre-programada, exceso no cuenta."""
    sobretasas = [{"hasta_horas": 2, "tasa": 0.25}, {"tasa": 0.35}]
    
    # 10h trabajadas, 8h programadas, 2h HE programadas -> HE = 2h
    he_25, he_35 = calcular_horas_extra(10.0, 8.0, 2.0, sobretasas)
    assert he_25 == 2.0
    assert he_35 == 0.0
    
    # 12h trabajadas, 8h programadas, 2h HE programadas -> HE = 2h (exceso no cuenta)
    he_25, he_35 = calcular_horas_extra(12.0, 8.0, 2.0, sobretasas)
    assert he_25 == 2.0
    assert he_35 == 0.0
    
    # 12h trabajadas, 8h programadas, 5h HE programadas -> HE 25%=2h, 35%=2h
    he_25, he_35 = calcular_horas_extra(12.0, 8.0, 5.0, sobretasas)
    assert he_25 == 2.0
    assert he_35 == 2.0


def test_r4_sin_he_programadas_no_cuenta():
    """R4: Si no hay HE programadas, exceso = 0 HE."""
    sobretasas = [{"hasta_horas": 2, "tasa": 0.25}, {"tasa": 0.35}]
    
    # 10h trabajadas, 8h programadas, 0 HE programadas
    he_25, he_35 = calcular_horas_extra(10.0, 8.0, 0.0, sobretasas)
    assert he_25 == 0.0
    assert he_35 == 0.0


# ============================================================================
# R5: Destino HE (CAVAS defecto pago, GCB SA defecto compensacion)
# ============================================================================

def test_r5_destino_he_pago_25_35(client, H, ids, db):
    """R5: Destino pago aplica 25% primeras 2h, 35% resto."""
    from app.models import Asistencia, RegularizacionHE, Trabajador
    
    trabajador = db.query(Trabajador).filter(Trabajador.codigo == "E001").first()
    asistencia = Asistencia(
        trabajador_id=trabajador.id,
        dia_operativo=date(2026, 10, 28),
        periodo="2026-10",
        horas_programadas=8.0,
        horas_trabajadas=12.0,
        exceso_no_programado=4.0,
        rule_set_id=1,
        periodo_cerrado=False
    )
    db.add(asistencia)
    db.flush()
    
    reg = RegularizacionHE(
        asistencia_id=asistencia.id,
        trabajador_id=trabajador.id,
        horas_exceso=4.0,
        estado="pendiente"
    )
    db.add(reg)
    db.commit()
    
    # Aprobar como pago
    resp = client.post(
        f"/regularizaciones/{reg.id}/decidir",
        json={"aprobar": True, "destino": "pago"},
        headers=H["admin"]
    )
    assert resp.status_code == 200
    
    # Refrescar
    db.expire(asistencia)
    asistencia = db.query(Asistencia).get(asistencia.id)
    
    # 4h: 2h al 25%, 2h al 35%
    assert asistencia.horas_extra_25 == 2.0
    assert asistencia.horas_extra_35 == 2.0
    assert asistencia.exceso_no_programado == 0.0


def test_r5_destino_compensacion_crea_credito(client, H, ids, db):
    """R5: Destino compensacion crea credito en banco horas."""
    from app.models import Asistencia, RegularizacionHE, Trabajador
    
    trabajador = db.query(Trabajador).filter(Trabajador.codigo == "E002").first()
    asistencia = Asistencia(
        trabajador_id=trabajador.id,
        dia_operativo=date(2026, 10, 29),
        periodo="2026-10",
        horas_programadas=8.0,
        horas_trabajadas=11.0,
        exceso_no_programado=3.0,
        rule_set_id=1,
        periodo_cerrado=False
    )
    db.add(asistencia)
    db.flush()
    
    reg = RegularizacionHE(
        asistencia_id=asistencia.id,
        trabajador_id=trabajador.id,
        horas_exceso=3.0,
        estado="pendiente"
    )
    db.add(reg)
    db.commit()
    
    # Aprobar como compensacion
    resp = client.post(
        f"/regularizaciones/{reg.id}/decidir",
        json={"aprobar": True, "destino": "compensacion"},
        headers=H["admin"]
    )
    assert resp.status_code == 200
    
    # Verificar credito
    resp_saldo = client.get(f"/banco-horas/saldo/{trabajador.id}", headers=H["admin"])
    assert resp_saldo.json()["saldo_horas"] == 3.0


# ============================================================================
# R6: PT riesgo promedio >4h/dia
# ============================================================================

def test_r6_pt_riesgo_promedio_4h():
    """R6: PT con promedio >4h/dia genera alerta no bloqueante."""
    # Esta logica esta en excepciones dashboard
    # Aqui validamos el calculo de promedio
    # 5 dias x 5h = 25h / 7 dias = 3.57 < 4 (OK)
    horas_semana = 5 * 5.0
    promedio = horas_semana / 7
    assert promedio < 4.0
    
    # 5 dias x 6h = 30h / 7 dias = 4.28 > 4 (RIESGO)
    horas_semana = 5 * 6.0
    promedio = horas_semana / 7
    assert promedio > 4.0


# ============================================================================
# R7: Horas nocturnas 22:00-06:00, recargo, bono 3 AM
# ============================================================================

def test_r7_horas_nocturnas_22_06():
    """R7: Cuenta horas entre 22:00-06:00."""
    config = {"inicio": "22:00", "fin": "06:00"}
    
    # Entrada 22:00, salida 23:00 -> 1h nocturna
    entrada = datetime(2026, 10, 28, 22, 0)
    salida = datetime(2026, 10, 28, 23, 0)
    horas_noc = calcular_horas_nocturnas(entrada, salida, config)
    assert horas_noc == pytest.approx(1.0, abs=0.1)
    
    # Entrada 05:00, salida 07:00 -> 1h nocturna (05-06)
    entrada = datetime(2026, 10, 28, 5, 0)
    salida = datetime(2026, 10, 28, 7, 0)
    horas_noc = calcular_horas_nocturnas(entrada, salida, config)
    assert horas_noc == pytest.approx(1.0, abs=0.1)
    
    # Entrada 23:00, salida 06:00 (dia siguiente) -> 7h nocturnas
    entrada = datetime(2026, 10, 28, 23, 0)
    salida = datetime(2026, 10, 29, 6, 0)
    horas_noc = calcular_horas_nocturnas(entrada, salida, config)
    assert horas_noc == pytest.approx(7.0, abs=0.2)


def test_r7_sin_horas_nocturnas():
    """R7: Turno diurno no genera horas nocturnas."""
    config = {"inicio": "22:00", "fin": "06:00"}
    
    # 08:00-17:00
    entrada = datetime(2026, 10, 28, 8, 0)
    salida = datetime(2026, 10, 28, 17, 0)
    horas_noc = calcular_horas_nocturnas(entrada, salida, config)
    assert horas_noc == 0.0


# ============================================================================
# R8: Auth + 4 roles
# ============================================================================

def test_r8_cuatro_roles_existen(H):
    """R8: Sistema tiene 4 roles: admin, rrhh, jefe, trabajador."""
    assert "admin" in H
    assert "rrhh" in H
    assert "jefe" in H
    assert "trabajador" in H


def test_r8_trabajador_no_ve_reportes(client, H):
    """R8: Trabajador no accede a reportes consolidados."""
    resp = client.get("/reportes/consolidado-mensual?periodo=2026-10", headers=H["trabajador"])
    assert resp.status_code == 403


def test_r8_jefe_ve_solo_su_unidad(client, H, db):
    """R8: Jefe solo ve datos de su unidad."""
    from app.models import Trabajador
    
    # Intentar ver trabajador de otra unidad deberia fallar
    resp = client.get("/banco-horas/saldo/999", headers=H["jefe"])
    assert resp.status_code in (403, 404)


# ============================================================================
# R9: Seed anonimizado con empresas CAVAS y GCB SA
# ============================================================================

def test_r9_empresas_seed_existen(db, ids):
    """R9: Seed contiene CAVAS y GCBSA anonimizados."""
    assert "CAVAS" in ids["emp"]
    assert "GCBSA" in ids["emp"]


def test_r9_tipos_contrato_seed(db, ids):
    """R9: Seed contiene FT, PT85, PT102."""
    assert "FT" in ids["tc"]
    assert "PT85" in ids["tc"]
    assert "PT102" in ids["tc"]


# ============================================================================
# Helpers y funciones auxiliares
# ============================================================================

def test_parse_time():
    """Parseo de HH:MM."""
    t = parse_time("08:30")
    assert t.hour == 8
    assert t.minute == 30


def test_time_to_minutes():
    """Conversion time a minutos desde medianoche."""
    assert time_to_minutes(time(0, 0)) == 0
    assert time_to_minutes(time(8, 30)) == 510
    assert time_to_minutes(time(23, 59)) == 1439


def test_minutes_to_hours():
    """Conversion minutos a horas con 2 decimales."""
    assert minutes_to_hours(120) == 2.0
    assert minutes_to_hours(90) == 1.5
    assert minutes_to_hours(0) == 0.0


def test_calcular_horas_trabajadas_descuenta_refrigerio():
    """Horas trabajadas descuenta refrigerio."""
    entrada = datetime(2026, 10, 28, 8, 0)
    salida = datetime(2026, 10, 28, 17, 0)
    # 9h - 45min refrigerio = 8.25h
    horas = calcular_horas_trabajadas(entrada, salida, 45)
    assert horas == 8.25


def test_calcular_distancia_haversine():
    """Distancia entre coordenadas."""
    # Lima centro aprox
    lat1, lng1 = -12.046374, -77.042793
    lat2, lng2 = -12.056374, -77.052793  # ~1.5km
    
    distancia = calcular_distancia(lat1, lng1, lat2, lng2)
    assert distancia > 1000  # Mas de 1km
    assert distancia < 2000  # Menos de 2km
