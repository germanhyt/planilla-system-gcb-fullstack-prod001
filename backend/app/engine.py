"""Motor de cálculo de asistencia y horas. Sprint 2."""
from datetime import date, datetime, time, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Optional

from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from .models import (
    Asistencia,
    HEProgramada,
    HorarioAsignacion,
    HorarioPlan,
    Marca,
    RegularizacionHE,
    RuleSet,
    TipoContrato,
    Trabajador,
    TurnoPlantilla,
)

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


def get_asignacion_vigente(db: Session, trabajador_id: int, dia: date) -> Optional[HorarioAsignacion]:
    """Asignación de horario que cubre el día (la de vigente_desde más reciente)."""
    return db.query(HorarioAsignacion).filter(
        HorarioAsignacion.trabajador_id == trabajador_id, HorarioAsignacion.vigente_desde <= dia,
        (HorarioAsignacion.vigente_hasta.is_(None)) | (HorarioAsignacion.vigente_hasta >= dia),
    ).order_by(HorarioAsignacion.vigente_desde.desc(), HorarioAsignacion.id.desc()).first()


def plantilla_de_asignacion(asig: HorarioAsignacion, dia: date) -> Optional[int]:
    """Plantilla del día según el patrón (rotación de N semanas desde la semana de vigente_desde)."""
    patron = asig.patron or []
    if not patron:
        return None
    lunes0 = asig.vigente_desde - timedelta(days=asig.vigente_desde.weekday())
    lunes = dia - timedelta(days=dia.weekday())
    semana = patron[((lunes - lunes0).days // 7) % len(patron)]
    return semana[dia.weekday()] if len(semana) == 7 else None


def resolver_turno_dia(db: Session, trabajador_id: int, dia: date) -> tuple[Optional[int], str]:
    """(plantilla_id, origen). Prioridad: plan semanal explícito > asignación vigente > sin horario."""
    plan = get_horario_plan_version(db, trabajador_id, dia)
    if plan:
        return get_turno_plantilla_dia(plan, dia), "plan_semanal"
    asig = get_asignacion_vigente(db, trabajador_id, dia)
    if asig:
        return plantilla_de_asignacion(asig, dia), "asignacion"
    return None, "sin_horario"


def refrigerio_efectivo(db: Session, trabajador: Trabajador, plantilla: TurnoPlantilla) -> int:
    """Refrigerio de la plantilla si está definido; si no, el del tipo de contrato (45 por defecto).

    Decisión PO: PT85/PT102 = 45 min (igual que FT); sigue configurable en tipo_contrato.refrigerio_min (0 = no se descuenta).
    """
    if plantilla.refrigerio_min is not None:
        return plantilla.refrigerio_min
    tc = db.get(TipoContrato, trabajador.tipo_contrato_id)
    return tc.refrigerio_min if tc and tc.refrigerio_min is not None else 45


def he_programadas_dia(db: Session, trabajador_id: int, dia: date) -> float:
    """HE preautorizadas (programadas por el jefe) vigentes para el día operativo; 0 si no hay."""
    h = db.query(HEProgramada).filter(HEProgramada.trabajador_id == trabajador_id, HEProgramada.dia == dia,
                                      HEProgramada.estado == "vigente").first()
    return float(h.horas) if h else 0.0


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
    """HE del 1.er tramo (hasta `sobretasas[0].hasta_horas`, 2 h por defecto) y del 2.º (resto); solo pre-programadas."""
    if he_programadas is None or he_programadas <= 0:
        return 0.0, 0.0
    
    exceso = max(0, horas_trabajadas - horas_programadas)
    he_efectivas = min(exceso, he_programadas)
    
    tope = next((float(s["hasta_horas"]) for s in sobretasas if s.get("hasta_horas")), 2.0)
    he_25 = min(he_efectivas, tope)
    he_35 = max(0, he_efectivas - tope)
    
    return round(he_25, 2), round(he_35, 2)


def calcular_asistencia_dia(
    db: Session,
    trabajador_id: int,
    dia_operativo: date,
    reglas: dict,
    he_programadas: Optional[float] = None,
) -> Optional[dict]:
    """Motor de cálculo diario. Retorna dict con los campos calculados o None si no hay marcas.

    - La entrada se busca en la ventana del día operativo [dia+corte, dia+1+corte) hora Lima.
    - La salida es la primera posterior a la entrada dentro de MAX_TURNO (turnos que cruzan el corte).
    - Las marcas diferidas (offline) se calculan con la hora del dispositivo.
    - he_programadas: HE preautorizadas del día. None = se leen de `he_programada` (programación del jefe).
    """
    from sqlalchemy import and_
    
    trabajador = db.query(Trabajador).get(trabajador_id)
    if not trabajador:
        return None
    
    rule_set = get_rule_set_vigente(db, trabajador.empresa_id, dia_operativo)
    
    corte = reglas["dia_operativo"]["corte"]
    periodo = get_periodo_operativo(dia_operativo, corte)
    
    turno_plantilla_id, _origen = resolver_turno_dia(db, trabajador_id, dia_operativo)
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
    
    if he_programadas is None:
        he_programadas = he_programadas_dia(db, trabajador_id, dia_operativo)

    horas_programadas = 0.0
    tardanza_min = 0
    refrigerio_min = 0
    
    if turno_plantilla:
        turno_inicio_min = time_to_minutes(turno_plantilla.inicio)
        turno_fin_min = time_to_minutes(turno_plantilla.fin)
        
        if turno_fin_min < turno_inicio_min:
            turno_fin_min += 1440
        
        duracion_min = turno_fin_min - turno_inicio_min
        refrigerio_min = refrigerio_efectivo(db, trabajador, turno_plantilla)
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


def recalcular_trabajador_periodo(db: Session, trabajador_id: int, periodo: str) -> bool:
    """Recalcula todas las asistencias de un trabajador en un periodo abierto.

    Idempotente y seguro con regularizaciones ya decididas: las asistencias se actualizan en
    sitio (no se borran si tienen regularizaciones aprobadas/rechazadas -> sin error de FK) y
    las decisiones del jefe se conservan; sólo las pendientes se regeneran. Devuelve False si
    el periodo está cerrado o el trabajador no existe.
    """
    from .cierre import esta_cerrado
    from .rules import efectivas

    trabajador = db.get(Trabajador, trabajador_id)
    if not trabajador:
        return False
    anio, mes = (int(x) for x in periodo.split("-"))
    fecha_inicio = date(anio, mes, 1)
    fecha_fin = date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)

    if esta_cerrado(db, trabajador.empresa_id, periodo) or db.query(Asistencia.id).filter(
            Asistencia.trabajador_id == trabajador_id, Asistencia.periodo == periodo,
            Asistencia.periodo_cerrado.is_(True)).first():
        return False

    existentes = {a.dia_operativo: a for a in db.query(Asistencia).filter(
        Asistencia.trabajador_id == trabajador_id, Asistencia.periodo == periodo)}
    ids = [a.id for a in existentes.values()] or [-1]
    # Sólo se regeneran las pendientes; las decididas se conservan (y su asistencia también).
    db.query(RegularizacionHE).filter(RegularizacionHE.estado == "pendiente",
                                      RegularizacionHE.asistencia_id.in_(ids)).delete(synchronize_session=False)
    decididas = {r.asistencia_id for r in db.query(RegularizacionHE.asistencia_id).filter(
        RegularizacionHE.asistencia_id.in_(ids))}

    # Reglas resueltas POR DIA: un rule_set nuevo a mitad de mes rige desde su valid_from (Sprint 6).
    versiones = db.query(RuleSet).filter(RuleSet.empresa_id == trabajador.empresa_id,
                                         RuleSet.valid_from < fecha_fin).order_by(RuleSet.valid_from).all()
    if not versiones:
        db.rollback()
        return False  # sin reglas vigentes (p. ej. antes del go-live): no hay nada que calcular
    cache: dict[int, dict] = {}

    def reglas_dia(d: date) -> Optional[dict]:
        rs = None
        for v in versiones:
            if v.valid_from <= d:
                rs = v
        if rs is None:
            return None
        if rs.id not in cache:
            cache[rs.id] = efectivas(rs.config)
        return cache[rs.id]

    dia_actual = fecha_inicio
    while dia_actual < fecha_fin:
        reglas = reglas_dia(dia_actual)
        resultado = calcular_asistencia_dia(db, trabajador_id, dia_actual, reglas) if reglas else None
        asistencia = existentes.pop(dia_actual, None)
        if resultado:
            if asistencia is None:
                asistencia = Asistencia(**resultado)
                db.add(asistencia)
            else:
                for k, v in resultado.items():
                    setattr(asistencia, k, v)
                asistencia.calculado_en = datetime.now(timezone.utc)
            db.flush()
            if resultado["exceso_no_programado"] > 0 and asistencia.id not in decididas:
                db.add(RegularizacionHE(asistencia_id=asistencia.id, trabajador_id=trabajador_id,
                                        horas_exceso=resultado["exceso_no_programado"]))
        elif asistencia is not None:
            existentes[dia_actual] = asistencia  # se evalúa abajo
        dia_actual += timedelta(days=1)

    # Días que ya no generan asistencia: se borran salvo que tengan decisiones (se conservan).
    for a in existentes.values():
        if a.id not in decididas:
            db.delete(a)
    db.commit()
    return True


def _periodos_entre(desde: date, hasta: date) -> list[str]:
    out, y, m = [], desde.year, desde.month
    while (y, m) <= (hasta.year, hasta.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def recalcular_rango(db: Session, trabajador_id: int, desde: date, hasta: Optional[date] = None) -> list[str]:
    """Disparo de recálculo tras cambios de HE programadas u horarios: recalcula los periodos
    abiertos afectados, sin pasar del mes actual. Devuelve los periodos recalculados."""
    hoy = date.today()
    hasta = min(hasta or hoy, hoy)
    if hasta < desde:
        hasta = desde
    return [p for p in _periodos_entre(desde, hasta) if recalcular_trabajador_periodo(db, trabajador_id, p)]
