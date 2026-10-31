"""Movimientos del banco de horas compensatorias (helpers compartidos)."""
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from .models import Asistencia, BancoHorasCompensatorias, Trabajador

ORIGEN_HE_PROG = "HE programada a compensacion"
DIAS_EXPIRACION = 90


def acreditar(db: Session, trabajador_id: int, dia: date, horas: float, origen: str,
              asistencia_id: Optional[int] = None, regularizacion_id: Optional[int] = None) -> BancoHorasCompensatorias:
    ultimo = db.query(BancoHorasCompensatorias).filter(BancoHorasCompensatorias.trabajador_id == trabajador_id) \
        .order_by(BancoHorasCompensatorias.creado_en.desc(), BancoHorasCompensatorias.id.desc()).first()
    anterior = float(ultimo.saldo_nuevo) if ultimo else 0.0
    mov = BancoHorasCompensatorias(trabajador_id=trabajador_id, fecha_movimiento=dia, tipo="credito", horas=horas,
                                   saldo_anterior=anterior, saldo_nuevo=round(anterior + horas, 2), origen=origen,
                                   asistencia_id=asistencia_id, regularizacion_id=regularizacion_id,
                                   dias_expiracion=DIAS_EXPIRACION, fecha_expira=dia + timedelta(days=DIAS_EXPIRACION))
    db.add(mov)
    db.flush()
    return mov


def acreditar_he_programadas(db: Session, empresa_id: int, periodo: str) -> int:
    """Al cerrar: acredita al banco las HE programadas con destino compensacion. Idempotente por asistencia
    (un re-cierre tras reapertura no duplica)."""
    ya = {a for (a,) in db.query(BancoHorasCompensatorias.asistencia_id).filter(
        BancoHorasCompensatorias.origen == ORIGEN_HE_PROG)}
    n = 0
    q = db.query(Asistencia).join(Trabajador, Trabajador.id == Asistencia.trabajador_id).filter(
        Trabajador.empresa_id == empresa_id, Asistencia.periodo == periodo, Asistencia.horas_extra_banco > 0) \
        .order_by(Asistencia.dia_operativo, Asistencia.id)
    for a in q:
        if a.id not in ya:
            acreditar(db, a.trabajador_id, a.dia_operativo, float(a.horas_extra_banco), ORIGEN_HE_PROG, asistencia_id=a.id)
            n += 1
    return n
