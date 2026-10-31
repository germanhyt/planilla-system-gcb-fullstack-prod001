"""Tests unitarios (funciones puras) del motor de cálculo.

Consolidado de test_engine.py + test_engine_golden_r1_r9.py (cubrían lo mismo dos veces).
Los casos end-to-end con BD están en test_engine_golden_cavas.py.
"""
from datetime import date, datetime, time

import pytest

from app.engine import (
    a_lima,
    calcular_distancia,
    calcular_horas_extra,
    calcular_horas_nocturnas,
    calcular_horas_trabajadas,
    calcular_tardanza,
    get_dia_operativo,
    get_periodo_operativo,
    minutes_to_hours,
    parse_time,
    time_to_minutes,
)

D = date(2025, 3, 3)
NOC = {"inicio": "22:00", "fin": "06:00"}
SOBRETASAS = [{"hasta_horas": 2, "tasa": 0.25}, {"tasa": 0.35}]


def at(hh, mm=0, dia=D):
    return datetime.combine(dia, time(hh, mm))


@pytest.mark.parametrize("a,b,lo,hi", [
    ((-9.531119, -77.530517), (-9.531500, -77.531000), 40, 80),
    ((-12.046374, -77.042793), (-12.056374, -77.052793), 1000, 2000),
])
def test_distancia_haversine(a, b, lo, hi):
    assert lo < calcular_distancia(*a, *b) < hi
    assert calcular_distancia(*a, *a) == 0


def test_helpers_tiempo():
    assert parse_time("08:30") == time(8, 30)
    assert [time_to_minutes(time(0)), time_to_minutes(time(8, 30)), time_to_minutes(time(23, 59))] == [0, 510, 1439]
    assert [minutes_to_hours(120), minutes_to_hours(90), minutes_to_hours(0)] == [2.0, 1.5, 0.0]


def test_a_lima_normaliza_aware_y_respeta_naive():
    from zoneinfo import ZoneInfo
    assert a_lima(datetime(2025, 3, 3, 13, 5, tzinfo=ZoneInfo("UTC"))) == at(8, 5)
    assert a_lima(at(8, 5)) == at(8, 5)


# R1: tolerancia
@pytest.mark.parametrize("modo,umbral,hh,mm,esperado", [
    ("umbral_perdona", 10, 7, 50, 0),
    ("umbral_perdona", 10, 8, 5, 0),
    ("umbral_perdona", 10, 8, 10, 0),
    ("umbral_perdona", 10, 8, 15, 15),
    ("umbral_descuenta_exceso", 10, 8, 10, 0),
    ("umbral_descuenta_exceso", 10, 8, 15, 5),
    ("umbral_descuenta_exceso", 10, 8, 20, 10),
    ("sin_tolerancia", 0, 8, 1, 1),
    ("sin_tolerancia", 0, 8, 0, 0),
])
def test_r1_tardanza(modo, umbral, hh, mm, esperado):
    assert calcular_tardanza(at(hh, mm), time(8), {"modo": modo, "minutos": umbral}) == esperado


# R2: día operativo
@pytest.mark.parametrize("ts,corte,dia", [
    (at(22, 0, date(2025, 3, 2)), "06:00", date(2025, 3, 2)),
    (at(3, 0), "06:00", date(2025, 3, 2)),      # salida de madrugada -> día anterior
    (at(5, 59), "06:00", date(2025, 3, 2)),
    (at(6, 0), "06:00", D),
    (at(8, 0), "06:00", D),
    (at(23, 0, date(2025, 3, 2)), "00:00", date(2025, 3, 2)),
    (at(0, 30), "00:00", D),                    # GCB: día calendario
])
def test_r2_dia_operativo(ts, corte, dia):
    assert get_dia_operativo(ts, corte) == dia


# R3: periodo = mes del día operativo (el corte se aplica una sola vez, en get_dia_operativo)
@pytest.mark.parametrize("corte", ["06:00", "00:00"])
def test_r3_periodo_es_mes_del_dia_operativo(corte):
    assert get_periodo_operativo(date(2025, 4, 1), corte) == "2025-04"
    assert get_periodo_operativo(date(2025, 3, 31), corte) == "2025-03"
    # Salida 01/04 03:00 con corte 06:00 -> día operativo 31/03 -> periodo marzo
    assert get_periodo_operativo(get_dia_operativo(datetime(2025, 4, 1, 3), "06:00"), "06:00") == "2025-03"


# R4: HE solo si fueron pre-programadas; 25 % primeras 2 h, 35 % resto
@pytest.mark.parametrize("trab,prog,he_prog,esperado", [
    (10.0, 8.0, 0.0, (0.0, 0.0)),
    (10.0, 8.0, None, (0.0, 0.0)),
    (10.0, 8.0, 2.0, (2.0, 0.0)),
    (12.0, 8.0, 2.0, (2.0, 0.0)),   # exceso sobre lo programado no cuenta
    (12.0, 8.0, 5.0, (2.0, 2.0)),
    (8.5, 8.0, 3.0, (0.5, 0.0)),    # programó más de lo trabajado
    (7.0, 8.0, 2.0, (0.0, 0.0)),    # no completó la jornada
])
def test_r4_horas_extra(trab, prog, he_prog, esperado):
    assert calcular_horas_extra(trab, prog, he_prog, SOBRETASAS) == esperado


# R7: nocturnas 22:00-06:00
@pytest.mark.parametrize("ent,sal,horas", [
    (at(22), at(23), 1.0),
    (at(5), at(7), 1.0),
    (at(23), at(6, 0, date(2025, 3, 4)), 7.0),
    (at(18), at(2, 30, date(2025, 3, 4)), 4.5),
    (at(8), at(17), 0.0),
])
def test_r7_horas_nocturnas(ent, sal, horas):
    assert calcular_horas_nocturnas(ent, sal, NOC) == horas


@pytest.mark.parametrize("ent,sal,refrigerio,horas", [
    (at(8), at(17), 45, 8.25),
    (at(8), at(17), 60, 8.0),
    (at(8), at(8, 30), 45, 0.0),   # nunca negativo
])
def test_horas_trabajadas_descuenta_refrigerio(ent, sal, refrigerio, horas):
    assert calcular_horas_trabajadas(ent, sal, refrigerio) == horas