"""Golden tests del motor con casos anonimizados representativos de Cavas.

Pasan por la BD (TurnoPlantilla + HorarioPlan + Marcas -> calcular_asistencia_dia /
recalcular_trabajador_periodo -> Asistencia / RegularizacionHE / alerta PT).
Fechas fijas en 2025-03 (pasado, sin depender del reloj ni del periodo abierto en dev);
cada test crea su propia empresa para no interferir con el seed ni con otros tests.
"""
from datetime import date, datetime, time, timedelta

import pytest
from zoneinfo import ZoneInfo

from app.engine import calcular_asistencia_dia, recalcular_trabajador_periodo
from app.models import (
    Asistencia,
    Empresa,
    HEProgramada,
    HorarioPlan,
    Marca,
    RegularizacionHE,
    RuleSet,
    TipoContrato,
    Trabajador,
    TurnoPlantilla,
    Unidad,
    Usuario,
)
from app.routers.bandeja import alertas_pt
from app.rules import CAVAS, efectivas

LIMA = ZoneInfo("America/Lima")
LUNES = date(2025, 3, 3)
REGLAS = efectivas(CAVAS)


def lima(d: date, hh: int, mm: int = 0, dias: int = 0) -> datetime:
    return datetime.combine(d + timedelta(days=dias), time(hh, mm), tzinfo=LIMA)


@pytest.fixture
def cavas(db, unique_id):
    """Empresa tipo Cavas (corte 06:00, tolerancia umbral_perdona 10 min) + unidad + turnos."""
    emp = Empresa(codigo=f"G{unique_id}", razon_social=f"Golden {unique_id}", ruc=f"20{unique_id[1:]}999")
    db.add(emp)
    db.flush()
    db.add(RuleSet(empresa_id=emp.id, version=1, valid_from=date(2020, 1, 1), config=CAVAS))
    uni = Unidad(empresa_id=emp.id, codigo="GU", nombre="Unidad golden")
    db.add(uni)
    db.flush()
    turnos = {
        "dia": TurnoPlantilla(unidad_id=uni.id, nombre="08-17", inicio=time(8), fin=time(17), refrigerio_min=60),
        "noche": TurnoPlantilla(unidad_id=uni.id, nombre="18-02", inicio=time(18), fin=time(2), refrigerio_min=45),
        "nocturno": TurnoPlantilla(unidad_id=uni.id, nombre="22-06", inicio=time(22), fin=time(6), refrigerio_min=0),
    }
    db.add_all(turnos.values())
    db.flush()
    creador = db.query(Usuario).first().id
    tcs = {t.codigo: t.id for t in db.query(TipoContrato).filter(TipoContrato.codigo.in_(("FT", "PT85", "PT102")))}
    n = 0

    def trabajador(turno: str | None = "dia", contrato: str = "FT") -> Trabajador:
        nonlocal n
        n += 1
        t = Trabajador(codigo=f"G{unique_id}{n}", empresa_id=emp.id, unidad_id=uni.id, doc_tipo="DNI",
                       doc_numero=f"9{unique_id[1:]}{n:02d}", nombres="Anon", apellidos=f"Golden {n}",
                       tipo_contrato_id=tcs[contrato], fecha_ingreso=date(2024, 1, 1))
        db.add(t)
        db.flush()
        if turno:
            tid = turnos[turno].id
            db.add(HorarioPlan(trabajador_id=t.id, semana_inicio=LUNES, version=1, creado_por=creador,
                               **{f"{d}_plantilla_id": tid for d in
                                  ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")}))
        db.flush()
        return t

    def marcar(t: Trabajador, entrada: datetime, salida: datetime):
        db.add_all([Marca(trabajador_id=t.id, tipo="entrada", ts_servidor=entrada, metodo="gps", validacion_estado="ok"),
                    Marca(trabajador_id=t.id, tipo="salida", ts_servidor=salida, metodo="gps", validacion_estado="ok")])
        db.commit()

    return trabajador, marcar


# --- Turno 08:00-17:00 (refrigerio 60) y tolerancia de 10 min -------------------------------
@pytest.mark.parametrize("hh,mm,tardanza", [(7, 55, 0), (8, 0, 0), (8, 10, 0), (8, 11, 11), (8, 25, 25)])
def test_turno_08_17_tardanza_umbral_10(db, cavas, hh, mm, tardanza):
    trabajador, marcar = cavas
    t = trabajador("dia")
    marcar(t, lima(LUNES, hh, mm), lima(LUNES, 17))
    r = calcular_asistencia_dia(db, t.id, LUNES, REGLAS)
    assert r["tardanza_min"] == tardanza
    assert r["horas_programadas"] == 8.0
    assert r["periodo"] == "2025-03"


def test_turno_08_17_jornada_exacta_sin_exceso(db, cavas):
    trabajador, marcar = cavas
    t = trabajador("dia")
    marcar(t, lima(LUNES, 8), lima(LUNES, 17))
    r = calcular_asistencia_dia(db, t.id, LUNES, REGLAS)
    assert (r["horas_trabajadas"], r["exceso_no_programado"], r["horas_nocturnas"]) == (8.0, 0, 0.0)


def test_hora_local_lima_aunque_la_marca_venga_en_utc(db, cavas):
    """08:05 Lima = 13:05 UTC: la tardanza se mide en hora local, no en UTC."""
    trabajador, marcar = cavas
    t = trabajador("dia")
    utc = ZoneInfo("UTC")
    marcar(t, lima(LUNES, 8, 5).astimezone(utc), lima(LUNES, 17).astimezone(utc))
    r = calcular_asistencia_dia(db, t.id, LUNES, REGLAS)
    assert (r["tardanza_min"], r["horas_trabajadas"], r["horas_nocturnas"]) == (0, 7.92, 0.0)


# --- Turno nocturno que termina 02:xx con corte 06:00 ------------------------------------------
def test_turno_noche_salida_02xx_cuenta_en_dia_operativo_de_inicio(db, cavas):
    trabajador, marcar = cavas
    t = trabajador("noche")
    marcar(t, lima(LUNES, 18), lima(LUNES, 2, 30, dias=1))
    r = calcular_asistencia_dia(db, t.id, LUNES, REGLAS)
    assert r["dia_operativo"] == LUNES
    assert r["horas_programadas"] == 7.25          # 8 h - 45 min
    assert r["horas_trabajadas"] == 7.75           # 8.5 h - 45 min
    assert r["horas_nocturnas"] == 4.5             # 22:00-02:30
    assert r["exceso_no_programado"] == 0.5
    # El martes no "hereda" la salida de las 02:30 ni crea asistencia fantasma
    assert calcular_asistencia_dia(db, t.id, LUNES + timedelta(days=1), REGLAS) is None


def test_turno_noche_fin_de_mes_queda_en_el_mes_del_dia_operativo(db, cavas):
    """Entrada 31/03 18:00, salida 01/04 02:10 -> día operativo 31/03, periodo 2025-03."""
    trabajador, marcar = cavas
    t = trabajador(None)
    d = date(2025, 3, 31)
    marcar(t, lima(d, 18), lima(d, 2, 10, dias=1))
    r = calcular_asistencia_dia(db, t.id, d, REGLAS)
    assert r["periodo"] == "2025-03"
    assert calcular_asistencia_dia(db, t.id, date(2025, 4, 1), REGLAS) is None


# --- Horas nocturnas 22:00-06:00 -------------------------------------------------------------
def test_nocturnas_turno_22_06_completo(db, cavas):
    """Salida exactamente a las 06:00 (= corte) sigue perteneciendo al turno que empezó a las 22:00."""
    trabajador, marcar = cavas
    t = trabajador("nocturno")
    marcar(t, lima(LUNES, 22), lima(LUNES, 6, dias=1))
    r = calcular_asistencia_dia(db, t.id, LUNES, REGLAS)
    assert (r["horas_trabajadas"], r["horas_nocturnas"], r["tardanza_min"]) == (8.0, 8.0, 0)


def test_nocturnas_parciales_turno_tarde(db, cavas):
    trabajador, marcar = cavas
    t = trabajador(None)
    marcar(t, lima(LUNES, 15), lima(LUNES, 23, 30))
    assert calcular_asistencia_dia(db, t.id, LUNES, REGLAS)["horas_nocturnas"] == 1.5


# --- Horas extra 25 % / 35 %: programadas vs no programadas ------------------------------------
@pytest.mark.parametrize("he_prog,he25,he35,exceso", [
    (0, 0.0, 0.0, 3.0),     # no programadas: todo a regularización
    (1, 1.0, 0.0, 2.0),     # programó 1 h, trabajó 3 h extra
    (3, 2.0, 1.0, 0.0),     # primeras 2 h al 25 %, la 3.ª al 35 %
    (5, 2.0, 1.0, 0.0),     # programar de más no paga horas no trabajadas
])
def test_horas_extra_programadas_vs_no_programadas(db, cavas, he_prog, he25, he35, exceso):
    trabajador, marcar = cavas
    t = trabajador("dia")
    marcar(t, lima(LUNES, 8), lima(LUNES, 20))   # 11 h netas, 8 programadas
    r = calcular_asistencia_dia(db, t.id, LUNES, REGLAS, he_programadas=he_prog)
    assert (r["horas_extra_25"], r["horas_extra_35"], r["exceso_no_programado"]) == (he25, he35, exceso)


def test_recalculo_periodo_exceso_no_programado_va_a_regularizacion(db, cavas):
    trabajador, marcar = cavas
    t = trabajador("dia")
    marcar(t, lima(LUNES, 8), lima(LUNES, 19, 30))          # 2.5 h de exceso
    marcar(t, lima(LUNES, 8, 20, dias=1), lima(LUNES, 17, dias=1))  # tardanza 20, sin exceso
    recalcular_trabajador_periodo(db, t.id, "2025-03")
    asis = {a.dia_operativo: a for a in db.query(Asistencia).filter_by(trabajador_id=t.id)}
    assert set(asis) == {LUNES, LUNES + timedelta(days=1)}
    assert asis[LUNES + timedelta(days=1)].tardanza_min == 20
    regs = db.query(RegularizacionHE).filter_by(trabajador_id=t.id).all()
    assert [(r.asistencia_id, float(r.horas_exceso), r.estado) for r in regs] == [(asis[LUNES].id, 2.5, "pendiente")]
    # Idempotente: recalcular no duplica asistencias ni regularizaciones
    recalcular_trabajador_periodo(db, t.id, "2025-03")
    assert db.query(Asistencia).filter_by(trabajador_id=t.id).count() == 2
    assert db.query(RegularizacionHE).filter_by(trabajador_id=t.id).count() == 1


def test_marca_diferida_se_calcula_con_hora_del_dispositivo(db, cavas):
    """Marca offline: se registró en el servidor horas después, pero cuenta la hora del equipo."""
    trabajador, _ = cavas
    t = trabajador("dia")
    db.add_all([
        Marca(trabajador_id=t.id, tipo="entrada", ts_servidor=lima(LUNES, 12), ts_cliente=lima(LUNES, 8, 2),
              metodo="gps", validacion_estado="ok", diferida=True, sincronizado_offline=True),
        Marca(trabajador_id=t.id, tipo="salida", ts_servidor=lima(LUNES, 17), metodo="gps", validacion_estado="ok"),
    ])
    db.commit()
    r = calcular_asistencia_dia(db, t.id, LUNES, REGLAS)
    assert (r["tardanza_min"], r["horas_trabajadas"]) == (0, 7.97)


@pytest.mark.parametrize("programadas,he25,he35,exceso", [
    (None, 0.0, 0.0, 3.0),  # sin programación del jefe: todo el exceso es no autorizado -> bandeja
    (2, 2.0, 0.0, 1.0),     # programó 2 h: se pagan al 25 %, la 3.ª va a la bandeja
    (3, 2.0, 1.0, 0.0),     # programó 3 h: 2 h al 25 % + 1 h al 35 %, nada a la bandeja
])
def test_he_programadas_por_el_jefe_conectadas_al_motor(db, cavas, programadas, he25, he35, exceso):
    """El motor lee la programación (he_programada) cuando no se le pasa he_programadas."""
    trabajador, marcar = cavas
    t = trabajador("dia")
    if programadas is not None:
        db.add(HEProgramada(trabajador_id=t.id, dia=LUNES, horas=programadas, creado_por=db.query(Usuario).first().id))
    marcar(t, lima(LUNES, 8), lima(LUNES, 20))   # 11 h netas, 8 programadas
    recalcular_trabajador_periodo(db, t.id, "2025-03")
    a = db.query(Asistencia).filter_by(trabajador_id=t.id, dia_operativo=LUNES).one()
    assert (float(a.horas_extra_25), float(a.horas_extra_35), float(a.exceso_no_programado)) == (he25, he35, exceso)
    assert float(a.horas_extra_programadas) == float(programadas or 0)
    regs = db.query(RegularizacionHE).filter_by(trabajador_id=t.id).all()
    assert [float(r.horas_exceso) for r in regs] == ([exceso] if exceso else [])


def test_he_programada_anulada_no_cuenta(db, cavas):
    trabajador, marcar = cavas
    t = trabajador("dia")
    db.add(HEProgramada(trabajador_id=t.id, dia=LUNES, horas=3, estado="anulada", creado_por=db.query(Usuario).first().id))
    marcar(t, lima(LUNES, 8), lima(LUNES, 20))
    r = calcular_asistencia_dia(db, t.id, LUNES, REGLAS)
    assert (r["horas_extra_25"], r["exceso_no_programado"]) == (0.0, 3.0)


# --- Part-time PT85/PT102: alerta si el promedio diario semanal > 4 h ---------------------------
@pytest.mark.parametrize("contrato,horas_dia,dias,alerta", [
    ("PT85", 5, 3, True),     # 5 h/día > 4
    ("PT102", 4, 5, False),   # justo 4 h/día: no supera
    ("PT102", 4.5, 4, True),
    ("FT", 9, 5, False),      # FT nunca genera alerta PT
])
def test_alerta_part_time_promedio_4h(db, cavas, contrato, horas_dia, dias, alerta):
    trabajador, marcar = cavas
    t = trabajador(None, contrato)
    for i in range(dias):
        ent = lima(LUNES, 9, dias=i)
        marcar(t, ent, ent + timedelta(hours=horas_dia))
    recalcular_trabajador_periodo(db, t.id, "2025-03")
    out = alertas_pt(db, Trabajador.id == t.id, LUNES, LUNES + timedelta(days=6))
    assert bool(out) is alerta
    if alerta:
        assert out[0]["contrato"] == contrato and out[0]["promedio"] == horas_dia and out[0]["dias"] == dias