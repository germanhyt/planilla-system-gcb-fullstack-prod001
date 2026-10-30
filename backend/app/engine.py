"""Motor de cálculo de asistencia y horas. Sprint 2."""
from datetime import date, datetime, time, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Optional

from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from .models import Asistencia, HorarioPlan, Marca, RegularizacionHE, RuleSet, Trabajador, TurnoPlantilla

LIMA = ZoneInfo("America/Lima")
# Ventana máxima para buscar la salida de un turno a partir de su entrada.
MAX_TURNO = timedelta(hours=20)


def a_lima(ts: datetime) -> datetime:
    """Normaliza a hora local de Lima (naive). Los naive se asumen ya en Lima."""
    if ts.tzinfo is None:
        return ts
    return ts.astimezone(LIMA).replace(tzinfo=None)


def ts_efectivo(m: Marca) -> datetime:
    """Hora que usa el cálculo: la del dispositivo si la marca es diferida (offline), si no la del servidor."""
    if getattr(m, "diferida", False) and m.ts_cliente is not None:
        return m.ts_cliente
    return m.ts_servidor


def calcular_distancia(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calcula distancia en metros usando fórmula haversine."""
    R = 6371000
    
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lng = radians(lng2 - lng1)
    
    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lng / 2) ** 2
    c = 2 * asin(sqrt(a))
    
    return R * c


def parse_time(t: str) -> time:
    """Parse HH:MM string to time."""
    h, m = t.split(":")
    return time(int(h), int(m))


def time_to_minutes(t: time) -> int:
    """Convert time to minutes since midnight."""
    return t.hour * 60 + t.minute


def minutes_to_hours(m: int) -> float:
    """Convert minutes to hours (2 decimals)."""
    return round(m / 60.0, 2)


def get_dia_operativo(ts: datetime, corte: str) -> date:
    """Calcula el día operativo según la hora de corte."""
    corte_time = parse_time(corte)
    if ts.time() < corte_time:
        return (ts.date() - timedelta(days=1))
    return ts.date()


def get_periodo_operativo(dia_op: date, corte: str) -> str:
    """Periodo YYYY-MM = mes calendario del día operativo (igual que cierre.py).

    El corte ya se aplicó al obtener el día operativo (get_dia_operativo): una marca
    del 01/11 02:00 con corte 06:00 pertenece al día operativo 31/10 -> periodo 10.
    Aplicarlo de nuevo aquí movía todo el 1.er día del mes al mes anterior.
    """
    return dia_op.strftime("%Y-%m")


def get_horario_plan_version(db: Session, trabajador_id: int, dia: date) -> Optional[HorarioPlan]:
    """Obtiene el plan de horario vigente para el día (última versión de esa semana)."""
    from sqlalchemy import and_
    
    dia_inicio_semana = dia - timedelta(days=dia.weekday())
    
    plan = db.query(HorarioPlan).filter(
        and_(
            HorarioPlan.trabajador_id == trabajador_id,
            HorarioPlan.semana_inicio == dia_inicio_semana
        )
    ).order_by(HorarioPlan.version.desc()).first()
    
    return plan


def get_turno_plantilla_dia(plan: HorarioPlan, dia: date) -> Optional[int]:
    """Devuelve el ID de la plantilla de turno para un día específico."""
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    dia_semana = dias[dia.weekday()]
    return getattr(plan, f"{dia_semana}_plantilla_id", None)


def get_rule_set_vigente(db: Session, empresa_id: int, dia: date) -> RuleSet:
    """Obtiene el rule_set vigente para la fecha dada."""
    from sqlalchemy import and_
    
    rule = db.query(RuleSet).filter(
        and_(
            RuleSet.empresa_id == empresa_id,
            RuleSet.valid_from <= dia
        )
    ).order_by(RuleSet.valid_from.desc()).first()
    
    if not rule:
        raise ValueError(f"No hay rule_set vigente para empresa {empresa_id} en {dia}")
    
    return rule


def calcular_tardanza(entrada_ts: datetime, turno_inicio: time, tolerancia_config: dict) -> int:
    """Calcula minutos de tardanza según el modo de tolerancia."""
    entrada_time = entrada_ts.time()
    entrada_min = time_to_minutes(entrada_time)
    inicio_min = time_to_minutes(turno_inicio)
    
    if entrada_min <= inicio_min:
        return 0
    
    retraso_min = entrada_min - inicio_min
    modo = tolerancia_config["modo"]
    umbral = tolerancia_config["minutos"]
    
    if modo == "umbral_perdona":
        return 0 if retraso_min <= umbral else retraso_min
    elif modo == "umbral_descuenta_exceso":
        return max(0, retraso_min - umbral)
    else:  # sin_tolerancia
        return retraso_min


def calcular_horas_nocturnas(entrada: datetime, salida: datetime, nocturno_config: dict) -> float:
    """Calcula horas nocturnas entre 22:00-06:00."""
    inicio_noc = parse_time(nocturno_config["inicio"])
    fin_noc = parse_time(nocturno_config["fin"])
    
    minutos_nocturnos = 0
    actual = entrada
    
    while actual < salida:
        hora_actual = actual.time()
        
        if (hora_actual >= inicio_noc or hora_actual < fin_noc):
            minutos_nocturnos += 1
        
        actual += timedelta(minutes=1)
    
    return minutes_to_hours(minutos_nocturnos)


def calcular_horas_trabajadas(entrada: datetime, salida: datetime, refrigerio_min: int) -> float:
    """Calcula horas trabajadas netas (descontando refrigerio)."""
    diff = salida - entrada
    minutos_totales = int(diff.total_seconds() / 60)
    minutos_netos = max(0, minutos_totales - refrigerio_min)
    return minutes_to_hours(minutos_netos)


def calcular_horas_extra(
    horas_trabajadas: float,
    horas_programadas: float,
    he_programadas: float,
    sobretasas: list[dict]
) -> tuple[float, float]:
    """Calcula HE 25% (primeras 2h) y 35% (resto) solo si fueron pre-programadas."""
    if he_programadas is None or he_programadas <= 0:
        return 0.0, 0.0
    
    exceso = max(0, horas_trabajadas - horas_programadas)
    he_efectivas = min(exceso, he_programadas)
    
    he_25 = min(he_efectivas, 2.0)
    he_35 = max(0, he_efectivas - 2.0)
    
    return round(he_25, 2), round(he_35, 2)


def calcular_asistencia_dia(
    db: Session,
    trabajador_id: int,
    dia_operativo: date,
    reglas: dict,
    he_programadas: float = 0.0,
) -> Optional[dict]:
    """Motor de cálculo diario. Retorna dict con los campos calculados o None si no hay marcas.

    - La entrada se busca en la ventana del día operativo [dia+corte, dia+1+corte) hora Lima.
    - La salida es la primera posterior a la entrada dentro de MAX_TURNO (turnos que cruzan el corte).
    - Las marcas diferidas (offline) se calculan con la hora del dispositivo.
    - he_programadas: HE pre-programadas del día (aún no hay almacenamiento; por defecto 0).
    """
    from sqlalchemy import and_
    
    trabajador = db.query(Trabajador).get(trabajador_id)
    if not trabajador:
        return None
    
    rule_set = get_rule_set_vigente(db, trabajador.empresa_id, dia_operativo)
    
    corte = reglas["dia_operativo"]["corte"]
    periodo = get_periodo_operativo(dia_operativo, corte)
    
    plan = get_horario_plan_version(db, trabajador_id, dia_operativo)
    turno_plantilla_id = get_turno_plantilla_dia(plan, dia_operativo) if plan else None
    turno_plantilla = db.query(TurnoPlantilla).get(turno_plantilla_id) if turno_plantilla_id else None
    
    dia_inicio = datetime.combine(dia_operativo, parse_time(corte))
    dia_fin = dia_inicio + timedelta(days=1)

    # Margen amplio en la consulta (servidor vs dispositivo y salida tras el corte); se filtra en Python.
    margen = timedelta(days=1)
    candidatas = db.query(Marca).filter(
        and_(
            Marca.trabajador_id == trabajador_id,
            Marca.ts_servidor >= (dia_inicio - margen).replace(tzinfo=LIMA),
            Marca.ts_servidor < (dia_fin + MAX_TURNO + margen).replace(tzinfo=LIMA),
            Marca.validacion_estado == "ok"
        )
    ).all()
    marcas = sorted(((a_lima(ts_efectivo(m)), m) for m in candidatas), key=lambda x: x[0])

    entrada_ts, entrada = next(((t, m) for t, m in marcas if m.tipo == "entrada" and dia_inicio <= t < dia_fin), (None, None))
    if not entrada:
        return None
    salida_ts, salida = next(((t, m) for t, m in marcas if m.tipo == "salida" and entrada_ts < t <= entrada_ts + MAX_TURNO), (None, None))
    if not salida:
        return None
    
    horas_programadas = 0.0
    tardanza_min = 0
    refrigerio_min = 0
    
    if turno_plantilla:
        turno_inicio_min = time_to_minutes(turno_plantilla.inicio)
        turno_fin_min = time_to_minutes(turno_plantilla.fin)
        
        if turno_fin_min < turno_inicio_min:
            turno_fin_min += 1440
        
        duracion_min = turno_fin_min - turno_inicio_min
        refrigerio_min = turno_plantilla.refrigerio_min
        horas_programadas = minutes_to_hours(duracion_min - refrigerio_min)
        
        tardanza_min = calcular_tardanza(entrada_ts, turno_plantilla.inicio, reglas["tolerancia"])
    
    horas_trabajadas = calcular_horas_trabajadas(entrada_ts, salida_ts, refrigerio_min)
    horas_nocturnas = calcular_horas_nocturnas(entrada_ts, salida_ts, reglas["nocturno"])
    
    he_25, he_35 = calcular_horas_extra(horas_trabajadas, horas_programadas, he_programadas, reglas["horas_extra"]["sobretasas"])
    
    exceso_no_prog = round(max(0, horas_trabajadas - horas_programadas - he_25 - he_35), 2)
    
    return {
        "trabajador_id": trabajador_id,
        "dia_operativo": dia_operativo,
        "periodo": periodo,
        "turno_plantilla_id": turno_plantilla_id,
        "entrada_marca_id": entrada.id,
        "salida_marca_id": salida.id,
        "horas_programadas": horas_programadas,
        "horas_trabajadas": horas_trabajadas,
        "tardanza_min": tardanza_min,
        "horas_extra_programadas": he_programadas,
        "horas_extra_25": he_25,
        "horas_extra_35": he_35,
        "horas_nocturnas": horas_nocturnas,
        "exceso_no_programado": exceso_no_prog,
        "rule_set_id": rule_set.id,
        "periodo_cerrado": False
    }


def recalcular_trabajador_periodo(db: Session, trabajador_id: int, periodo: str):
    """RQ job: recalcula todas las asistencias de un trabajador en un periodo."""
    from sqlalchemy import and_

    from .rules import efectivas
    
    trabajador = db.query(Trabajador).get(trabajador_id)
    if not trabajador:
        return
    
    anio, mes = periodo.split("-")
    fecha_inicio = date(int(anio), int(mes), 1)
    
    if mes == "12":
        fecha_fin = date(int(anio) + 1, 1, 1)
    else:
        fecha_fin = date(int(anio), int(mes) + 1, 1)
    
    cerrada = db.query(Asistencia).filter(
        and_(
            Asistencia.trabajador_id == trabajador_id,
            Asistencia.periodo == periodo,
            Asistencia.periodo_cerrado
        )
    ).first()
    
    if cerrada:
        return
    
    del_periodo = and_(Asistencia.trabajador_id == trabajador_id, Asistencia.periodo == periodo)
    # Primero las regularizaciones pendientes DEL PERIODO (FK a asistencia); antes se borraban
    # todas las del trabajador (otros periodos incluidos) y después de la asistencia -> FK error.
    db.query(RegularizacionHE).filter(
        RegularizacionHE.estado == "pendiente",
        RegularizacionHE.asistencia_id.in_(db.query(Asistencia.id).filter(del_periodo)),
    ).delete(synchronize_session=False)
    db.query(Asistencia).filter(del_periodo).delete(synchronize_session=False)
    
    rule_set = get_rule_set_vigente(db, trabajador.empresa_id, fecha_inicio)
    reglas = efectivas(rule_set.config)
    
    dia_actual = fecha_inicio
    while dia_actual < fecha_fin:
        resultado = calcular_asistencia_dia(db, trabajador_id, dia_actual, reglas)
        
        if resultado:
            asistencia = Asistencia(**resultado)
            db.add(asistencia)
            db.flush()
            
            if resultado["exceso_no_programado"] > 0:
                regularizacion = RegularizacionHE(
                    asistencia_id=asistencia.id,
                    trabajador_id=trabajador_id,
                    horas_exceso=resultado["exceso_no_programado"]
                )
                db.add(regularizacion)
        
        dia_actual += timedelta(days=1)
    
    db.commit()
