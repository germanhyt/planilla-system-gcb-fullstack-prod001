"""Sprint 7: alertas internas para RRHH (tabla `notificacion`, sin correo).

Tipos:
- asistencia_decidida_sin_marcas: un recalculo conserva una asistencia con HE ya decidida, pero el dia ya no
  genera asistencia (p. ej. se anularon/corrigieron las marcas). La detecta el motor al recalcular.
- pendientes_cierre: faltando <= N dias para el fin del periodo (o vencido) y sin cerrar, hay HE sin decidir,
  excepciones (fuera de geocerca) o marcas incompletas.
- pt_riesgo: part-time con promedio semanal > umbral (criterio de la bandeja).
- bonos_sin_aprobar: bonos 3 AM registrados sin aprobar en el periodo.
Cada alerta tiene una `clave` unica: regenerar no duplica; si la condicion desaparece queda activa=False.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from .models import Notificacion, Trabajador

DIAS_AVISO_CIERRE = 5
GENERADAS = ("pendientes_cierre", "pt_riesgo", "bonos_sin_aprobar")


def upsert(db: Session, empresa_id: int, periodo: str, tipo: str, clave: str, mensaje: str,
           datos: Optional[dict] = None) -> Notificacion:
    n = db.query(Notificacion).filter(Notificacion.clave == clave).first()
    if n is None:
        n = Notificacion(empresa_id=empresa_id, periodo=periodo, tipo=tipo, clave=clave, mensaje=mensaje, datos=datos,
                         activa=True)
        db.add(n)
    else:
        if not n.activa:  # reaparece: vuelve a no leida
            n.activa, n.leida_por, n.leida_en = True, None, None
        n.mensaje, n.datos = mensaje, datos
    db.flush()
    return n


def resolver(db: Session, clave: str) -> None:
    n = db.query(Notificacion).filter(Notificacion.clave == clave, Notificacion.activa.is_(True)).first()
    if n:
        n.activa = False


def asistencia_sin_marcas(db: Session, trabajador: Trabajador, asistencia) -> None:
    upsert(db, trabajador.empresa_id, asistencia.periodo, "asistencia_decidida_sin_marcas",
           f"sin_marcas:{asistencia.id}",
           f"{trabajador.codigo} {trabajador.nombres} {trabajador.apellidos}: la asistencia del "
           f"{asistencia.dia_operativo.isoformat()} tiene HE decidida pero ya no tiene marcas que la sustenten.",
           {"trabajador_id": trabajador.id, "asistencia_id": asistencia.id,
            "dia": asistencia.dia_operativo.isoformat()})


def generar(db: Session, empresa_id: int, periodo: str, hoy: Optional[date] = None) -> dict:
    """(Re)genera las alertas calculables del periodo. Idempotente. Devuelve conteos activos por tipo."""
    from .cierre import checklist
    from .routers.bandeja import alertas_pt
    from .routers.reportes import rango

    hoy = hoy or datetime.now(timezone.utc).date()
    desde, hasta = rango(periodo)
    chk = checklist(db, empresa_id, periodo)
    vigentes: set[str] = set()

    def _alta(tipo, clave, mensaje, datos):
        upsert(db, empresa_id, periodo, tipo, clave, mensaje, datos)
        vigentes.add(clave)

    c = chk["conteos"]
    pendientes = c["he_sin_decidir"] + c["excepciones_pendientes"] + c["marcas_incompletas"]
    if not chk["cerrado"] and hoy >= hasta - timedelta(days=DIAS_AVISO_CIERRE) and pendientes:
        _alta("pendientes_cierre", f"pendientes_cierre:{empresa_id}:{periodo}",
              f"Cierre {periodo} {'vencido' if hoy > hasta else 'proximo (' + hasta.isoformat() + ')'}: "
              f"{c['he_sin_decidir']} HE sin decidir, {c['excepciones_pendientes']} excepciones, "
              f"{c['marcas_incompletas']} marcas incompletas.",
              {k: c[k] for k in ("he_sin_decidir", "excepciones_pendientes", "marcas_incompletas")}
              | {"fin_periodo": hasta.isoformat()})
    if c["bonos_sin_aprobar"] and not chk["cerrado"]:
        _alta("bonos_sin_aprobar", f"bonos_sin_aprobar:{empresa_id}:{periodo}",
              f"{c['bonos_sin_aprobar']} bono(s) 3 AM del periodo {periodo} sin aprobar.",
              {"cantidad": c["bonos_sin_aprobar"], "ids": [b["ref_id"] for b in chk["bonos_sin_aprobar"]]})
    for a in alertas_pt(db, Trabajador.empresa_id == empresa_id, desde, hasta):
        t = a["trabajador"]
        _alta("pt_riesgo", f"pt_riesgo:{t.id}:{a['semana'].isoformat()}",
              f"{t.codigo} {t.nombres} {t.apellidos} ({a['contrato']}): promedio {a['promedio']} h/dia trabajado "
              f"la semana del {a['semana'].isoformat()} (umbral {a['umbral']} h).",
              {"trabajador_id": t.id, "semana": a["semana"].isoformat(), "promedio": a["promedio"],
               "umbral": a["umbral"]})
    for n in db.query(Notificacion).filter(Notificacion.empresa_id == empresa_id, Notificacion.periodo == periodo,
                                           Notificacion.tipo.in_(GENERADAS), Notificacion.activa.is_(True)):
        if n.clave not in vigentes:
            n.activa = False
    db.flush()
    activas = db.query(Notificacion).filter(Notificacion.empresa_id == empresa_id, Notificacion.periodo == periodo,
                                            Notificacion.activa.is_(True)).all()
    out: dict[str, int] = {}
    for n in activas:
        out[n.tipo] = out.get(n.tipo, 0) + 1
    return out
