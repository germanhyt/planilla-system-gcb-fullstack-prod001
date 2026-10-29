"""Motor de cálculo de asistencia y horas. Sprint 2."""
from datetime import date, datetime, time, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Optional

from sqlalchemy.orm import Session

from .models import Asistencia, HorarioPlan, Marca, RegularizacionHE, RuleSet, Trabajador, TurnoPlantilla


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
    """Calcula el periodo YYYY-MM según el día operativo y el corte.
    
    Si el corte es > 00:00, los primeros días del mes pueden pertenecer al mes anterior.
    """
    corte_time = parse_time(corte)
    if corte_time > time(0, 0):
        if dia_op.day == 1:
            mes_anterior = dia_op - timedelta(days=1)
            return mes_anterior.strftime("%Y-%m")
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
    reglas: dict
) -> Optional[dict]:
    """Motor de cálculo diario. Retorna dict con los campos calculados o None si no hay marcas."""
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
    
    dia_inicio = datetime.combine(dia_operativo, parse_time("00:00"))
    dia_fin = dia_inicio + timedelta(days=1)
    
    marcas = db.query(Marca).filter(
        and_(
            Marca.trabajador_id == trabajador_id,
            Marca.ts_servidor >= dia_inicio,
            Marca.ts_servidor < dia_fin,
            Marca.validacion_estado == "ok"
        )
    ).order_by(Marca.ts_servidor).all()
    
    if not marcas:
        return None
    
    entrada = next((m for m in marcas if m.tipo == "entrada"), None)
    salida = next((m for m in marcas if m.tipo == "salida" and m.ts_servidor > (entrada.ts_servidor if entrada else dia_inicio)), None)
    
    if not entrada or not salida:
        return None
    
    horas_programadas = 0.0
    he_programadas = 0.0
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
        
        tardanza_min = calcular_tardanza(entrada.ts_servidor, turno_plantilla.inicio, reglas["tolerancia"])
    
    horas_trabajadas = calcular_horas_trabajadas(entrada.ts_servidor, salida.ts_servidor, refrigerio_min)
    horas_nocturnas = calcular_horas_nocturnas(entrada.ts_servidor, salida.ts_servidor, reglas["nocturno"])
    
    he_25, he_35 = calcular_horas_extra(horas_trabajadas, horas_programadas, he_programadas, reglas["horas_extra"]["sobretasas"])
    
    exceso_no_prog = max(0, horas_trabajadas - horas_programadas - he_25 - he_35)
    
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
    
    db.query(Asistencia).filter(
        and_(
            Asistencia.trabajador_id == trabajador_id,
            Asistencia.periodo == periodo
        )
    ).delete()
    
    db.query(RegularizacionHE).filter(
        RegularizacionHE.trabajador_id == trabajador_id
    ).filter(
        RegularizacionHE.estado == "pendiente"
    ).delete()
    
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
