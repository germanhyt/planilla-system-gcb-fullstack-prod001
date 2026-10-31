"""Movimientos del banco de horas compensatorias (helpers compartidos)."""
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from .models import Asistencia, BancoHorasCompensatorias, Trabajador

ORIGEN_HE_PROG = "HE programada a compensacion"
ORIGEN_AJUSTE = "Ajuste HE programada (re-cierre)"
DIAS_EXPIRACION = 90


def mover(db: Session, trabajador_id: int, dia: date, horas: float, origen: str,
          asistencia_id: Optional[int] = None, regularizacion_id: Optional[int] = None) -> BancoHorasCompensatorias:
    """Movimiento del banco: horas > 0 -> credito, horas < 0 -> debito. El saldo se encadena al ultimo movimiento."""
    ultimo = db.query(BancoHorasCompensatorias).filter(BancoHorasCompensatorias.trabajador_id == trabajador_id) \
        .order_by(BancoHorasCompensatorias.creado_en.desc(), BancoHorasCompensatorias.id.desc()).first()
    anterior = float(ultimo.saldo_nuevo) if ultimo else 0.0
    credito = horas > 0
    mov = BancoHorasCompensatorias(trabajador_id=trabajador_id, fecha_movimiento=dia,
                                   tipo="credito" if credito else "debito", horas=abs(horas),
                                   saldo_anterior=anterior, saldo_nuevo=round(anterior + horas, 2), origen=origen,
                                   asistencia_id=asistencia_id, regularizacion_id=regularizacion_id,
                                   dias_expiracion=DIAS_EXPIRACION if credito else None,
                                   fecha_expira=dia + timedelta(days=DIAS_EXPIRACION) if credito else None)
    db.add(mov)
    db.flush()
    return mov


def acreditar(db: Session, trabajador_id: int, dia: date, horas: float, origen: str,
              asistencia_id: Optional[int] = None, regularizacion_id: Optional[int] = None) -> BancoHorasCompensatorias:
    return mover(db, trabajador_id, dia, abs(horas), origen, asistencia_id, regularizacion_id)


def acreditar_he_programadas(db: Session, empresa_id: int, periodo: str) -> dict:
    """Al cerrar: concilia el banco con las HE programadas a compensacion del periodo, por (trabajador, dia).
    deseado = asistencia.horas_extra_banco; acreditado = neto de movimientos HE_PROG + AJUSTE ya posteados.
    Primer cierre -> credito HE_PROG; re-cierre tras reapertura -> solo el DELTA como movimiento de ajuste
    (credito o debito). Sin cambios -> ningun movimiento (no hay doble conteo)."""
    from .routers.reportes import rango
    desde, hasta = rango(periodo)
    deseado: dict = {}
    q = db.query(Asistencia).join(Trabajador, Trabajador.id == Asistencia.trabajador_id).filter(
        Trabajador.empresa_id == empresa_id, Asistencia.periodo == periodo)
    for a in q:
        deseado[(a.trabajador_id, a.dia_operativo)] = (round(float(a.horas_extra_banco or 0), 2), a.id)
    posteado: dict = {}
    movs = db.query(BancoHorasCompensatorias).join(Trabajador, Trabajador.id == BancoHorasCompensatorias.trabajador_id) \
        .filter(Trabajador.empresa_id == empresa_id, BancoHorasCompensatorias.origen.in_((ORIGEN_HE_PROG, ORIGEN_AJUSTE)),
                BancoHorasCompensatorias.fecha_movimiento >= desde, BancoHorasCompensatorias.fecha_movimiento <= hasta)
    for m in movs:
        k = (m.trabajador_id, m.fecha_movimiento)
        posteado[k] = posteado.get(k, 0.0) + (float(m.horas) if m.tipo == "credito" else -float(m.horas))
    res = {"creditos": 0, "horas_acreditadas": 0.0, "ajustes": []}
    for k in sorted(set(deseado) | set(posteado)):
        quiere, aid = deseado.get(k, (0.0, None))
        ya = round(posteado.get(k, 0.0), 2)
        delta = round(quiere - ya, 2)
        if abs(delta) < 0.01:
            continue
        tid, dia = k
        if k not in posteado:
            mover(db, tid, dia, delta, ORIGEN_HE_PROG, asistencia_id=aid)
            res["creditos"] += 1
            res["horas_acreditadas"] = round(res["horas_acreditadas"] + delta, 2)
        else:
            mov = mover(db, tid, dia, delta, ORIGEN_AJUSTE, asistencia_id=aid)
            res["ajustes"].append({"trabajador_id": tid, "dia": dia.isoformat(), "antes": ya, "despues": quiere,
                                   "delta": delta, "movimiento_id": mov.id})
    return res
