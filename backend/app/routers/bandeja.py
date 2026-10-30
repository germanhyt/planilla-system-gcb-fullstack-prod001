"""Sprint 3 / Incremento 2: bandeja unificada de excepciones y bolsa (banco) de horas por trabajador.

- HE: sólo las preautorizadas por el jefe se pagan automáticamente; el exceso no programado llega como
  "he_no_programada" (no autorizado) a la bandeja del jefe para regularización opcional.
- Destino HE flexible al aprobar: pago (25%/35%), compensación (banco de horas) o mixto.
  Por defecto: el destino_default del rule_set vigente (CAVAS=pago, GCB SA=compensación).
- Alerta PT85/PT102 si el promedio semanal supera 4 h/día trabajado (informativa, no bloquea).
"""
from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import false, func, select, true
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from ..db import get_db
from ..deps import current_user
from ..models import (
    Asistencia,
    BancoHorasCompensatorias,
    Empresa,
    Marca,
    RegularizacionHE,
    RuleSet,
    TipoContrato,
    Trabajador,
    Usuario,
)
from ..rules import efectivas
from .reglas import vigente

LIMA = ZoneInfo("America/Lima")
router = APIRouter(prefix="/excepciones", tags=["excepciones"])
banco = APIRouter(prefix="/banco-horas", tags=["banco_horas"])

TIPOS = ("he_no_programada", "tardanza", "fuera_geocerca", "marca_diferida", "pt_alerta")
GESTORES = ("jefe", "rrhh", "admin")


def _alcance(db: Session, u: Usuario, unidad_id: Optional[int]):
    """Filtro de trabajadores según rol: jefe sólo su unidad; RRHH/admin todo (o la unidad pedida)."""
    if u.rol not in GESTORES:
        raise HTTPException(403, "No autorizado")
    if u.rol == "jefe":
        if not u.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        return Trabajador.unidad_id == u.unidad_id
    return Trabajador.unidad_id == unidad_id if unidad_id else true()


def _reglas(db: Session, empresa_id: int, dia: date) -> dict:
    """Reglas efectivas del rule_set vigente al día; si el día es anterior a todos, usa la primera versión."""
    rs = vigente(db, empresa_id, dia) or db.scalar(
        select(RuleSet).where(RuleSet.empresa_id == empresa_id).order_by(RuleSet.valid_from).limit(1))
    return efectivas(rs.config or {} if rs else {})


def destino_default(db: Session, empresa_id: int, dia: date) -> str:
    return _reglas(db, empresa_id, dia)["horas_extra"]["destino_default"]


def umbral_pt(db: Session, empresa_id: int, dia: date) -> float:
    return float(_reglas(db, empresa_id, dia)["part_time"]["alerta_promedio_diario_horas"])


def _trab(t: Trabajador) -> dict:
    return {"id": t.id, "codigo": t.codigo, "nombre": f"{t.nombres} {t.apellidos}", "unidad_id": t.unidad_id}


def alertas_pt(db: Session, filtro, desde: date, hasta: date) -> list[dict]:
    """Semanas (lun-dom) que tocan [desde, hasta] donde un PT85/PT102 promedia > umbral h por día trabajado."""
    lunes = desde - timedelta(days=desde.weekday())
    fin = hasta - timedelta(days=hasta.weekday()) + timedelta(days=7)
    semana = func.date_trunc("week", Asistencia.dia_operativo)
    filas = db.execute(
        select(Trabajador, TipoContrato.codigo, semana.label("sem"), func.sum(Asistencia.horas_trabajadas),
               func.count(Asistencia.id))
        .join(Asistencia, Asistencia.trabajador_id == Trabajador.id)
        .join(TipoContrato, TipoContrato.id == Trabajador.tipo_contrato_id)
        .where(filtro, TipoContrato.codigo.in_(("PT85", "PT102")), Asistencia.dia_operativo >= lunes,
               Asistencia.dia_operativo < fin, Asistencia.horas_trabajadas.isnot(None))
        .group_by(Trabajador.id, TipoContrato.codigo, semana)).all()
    out = []
    for t, tc, sem, total, dias in filas:
        sem_d = sem.date() if hasattr(sem, "date") else sem
        prom = float(total) / dias if dias else 0.0
        umbral = umbral_pt(db, t.empresa_id, sem_d)
        if prom > umbral:
            out.append({"trabajador": t, "contrato": tc, "semana": sem_d, "promedio": round(prom, 2),
                        "total": round(float(total), 2), "dias": dias, "umbral": umbral})
    return out


@router.get("/bandeja")
def bandeja(
    desde: date = Query(...),
    hasta: date = Query(...),
    tipo: Optional[Literal["he_no_programada", "tardanza", "fuera_geocerca", "marca_diferida", "pt_alerta"]] = None,
    estado: Optional[Literal["pendiente", "aprobado", "rechazado", "informativo"]] = None,
    unidad_id: Optional[int] = None,
    db: Session = Depends(get_db),
    u: Usuario = Depends(current_user),
):
    """Bandeja unificada de excepciones. Jefe: su unidad. RRHH/admin: todas. Trabajador: 403."""
    filtro = _alcance(db, u, unidad_id)
    if hasta < desde:
        raise HTTPException(400, "Rango inválido")
    items: list[dict] = []
    pt_por_trab: dict[int, list[dict]] = {}
    for a in alertas_pt(db, filtro, desde, hasta):
        pt_por_trab.setdefault(a["trabajador"].id, []).append(a)

    if tipo in (None, "he_no_programada"):
        q = (select(RegularizacionHE, Asistencia, Trabajador, Empresa)
             .join(Asistencia, Asistencia.id == RegularizacionHE.asistencia_id)
             .join(Trabajador, Trabajador.id == RegularizacionHE.trabajador_id)
             .join(Empresa, Empresa.id == Trabajador.empresa_id)
             .where(filtro, Asistencia.dia_operativo >= desde, Asistencia.dia_operativo <= hasta))
        if estado in ("pendiente", "aprobado", "rechazado"):
            q = q.where(RegularizacionHE.estado == estado)
        elif estado == "informativo":
            q = q.where(false())
        for reg, asi, t, emp in db.execute(q.order_by(Asistencia.dia_operativo.desc(), RegularizacionHE.id.desc())):
            sem = asi.dia_operativo - timedelta(days=asi.dia_operativo.weekday())
            alerta = next((a for a in pt_por_trab.get(t.id, []) if a["semana"] == sem), None)
            items.append({
                "clave": f"he-{reg.id}", "tipo": "he_no_programada", "ref_id": reg.id, "trabajador": _trab(t),
                "empresa": emp.codigo, "dia": asi.dia_operativo.isoformat(),
                "detalle": f"{float(reg.horas_exceso):.2f} h de exceso no programado (no autorizado)",
                "horas": float(reg.horas_exceso), "estado": reg.estado, "destino": reg.destino,
                "destino_default": destino_default(db, t.empresa_id, asi.dia_operativo),
                "observacion": reg.observacion, "accionable": reg.estado == "pendiente",
                "alerta_pt": f"{alerta['contrato']}: promedio {alerta['promedio']} h/día en la semana" if alerta else None,
            })

    if tipo in (None, "tardanza") and estado in (None, "informativo"):
        q = (select(Asistencia, Trabajador).join(Trabajador, Trabajador.id == Asistencia.trabajador_id)
             .where(filtro, Asistencia.tardanza_min > 0, Asistencia.dia_operativo >= desde,
                    Asistencia.dia_operativo <= hasta).order_by(Asistencia.dia_operativo.desc()).limit(300))
        for asi, t in db.execute(q):
            items.append({"clave": f"tar-{asi.id}", "tipo": "tardanza", "ref_id": asi.id, "trabajador": _trab(t),
                          "dia": asi.dia_operativo.isoformat(), "detalle": f"Tardanza de {asi.tardanza_min} min",
                          "estado": "informativo", "accionable": False})

    if tipo in (None, "fuera_geocerca") and estado in (None, "informativo"):
        q = (select(Marca, Trabajador).join(Trabajador, Trabajador.id == Marca.trabajador_id)
             .where(filtro, Marca.validacion_estado == "fuera_geocerca",
                    func.date(func.timezone("America/Lima", Marca.ts_servidor)) >= desde,
                    func.date(func.timezone("America/Lima", Marca.ts_servidor)) <= hasta)
             .order_by(Marca.ts_servidor.desc()).limit(300))
        for m, t in db.execute(q):
            dist = f" a {round(float(m.distancia_m))} m" if m.distancia_m is not None else ""
            items.append({"clave": f"geo-{m.id}", "tipo": "fuera_geocerca", "ref_id": m.id, "trabajador": _trab(t),
                          "dia": m.ts_servidor.date().isoformat(), "detalle": f"Marca de {m.tipo} fuera de geocerca{dist}",
                          "estado": "informativo", "accionable": False})

    if tipo in (None, "marca_diferida") and estado in (None, "informativo"):
        from .marcas import umbral_diferida
        q = (select(Marca, Trabajador).join(Trabajador, Trabajador.id == Marca.trabajador_id)
             .where(filtro, Marca.diferida.is_(True), Marca.diferencia_min.isnot(None),
                    func.date(func.timezone("America/Lima", Marca.ts_servidor)) >= desde,
                    func.date(func.timezone("America/Lima", Marca.ts_servidor)) <= hasta)
             .order_by(Marca.ts_servidor.desc()).limit(300))
        for m, t in db.execute(q):
            umbral = umbral_diferida(db, t.empresa_id, m.ts_servidor.date())
            if m.diferencia_min <= umbral:
                continue
            disp = m.ts_cliente.astimezone(LIMA).strftime("%d/%m %H:%M") if m.ts_cliente else "?"
            items.append({"clave": f"dif-{m.id}", "tipo": "marca_diferida", "ref_id": m.id, "trabajador": _trab(t),
                          "dia": m.ts_servidor.astimezone(LIMA).date().isoformat(),
                          "detalle": (f"Marca de {m.tipo} sincronizada offline {m.diferencia_min} min despues"
                                      f" (dispositivo {disp}; umbral {umbral} min). Revisar"),
                          "estado": "informativo", "accionable": False})

    if tipo in (None, "pt_alerta") and estado in (None, "informativo"):
        for lista in pt_por_trab.values():
            for a in lista:
                items.append({"clave": f"pt-{a['trabajador'].id}-{a['semana']}", "tipo": "pt_alerta", "ref_id": None,
                              "trabajador": _trab(a["trabajador"]), "dia": a["semana"].isoformat(),
                              "detalle": (f"{a['contrato']}: promedio {a['promedio']} h/día ({a['total']} h en {a['dias']} días)"
                                          f" > {a['umbral']:g} h/día. Alerta no bloqueante"),
                              "estado": "informativo", "accionable": False})
    items.sort(key=lambda i: i["dia"], reverse=True)
    return items


def _saldo(db: Session, trabajador_id: int) -> float:
    ult = db.scalar(select(BancoHorasCompensatorias.saldo_nuevo)
                    .where(BancoHorasCompensatorias.trabajador_id == trabajador_id)
                    .order_by(BancoHorasCompensatorias.creado_en.desc(), BancoHorasCompensatorias.id.desc()).limit(1))
    return float(ult) if ult is not None else 0.0


@banco.get("/saldos")
def saldos(unidad_id: Optional[int] = None, solo_con_movimientos: bool = False, db: Session = Depends(get_db),
           u: Usuario = Depends(current_user)):
    """Saldo de la bolsa de horas por trabajador. Trabajador: sólo el suyo; jefe: su unidad; RRHH/admin: todos."""
    if u.rol == "trabajador":
        filtro = Trabajador.usuario_id == u.id
    else:
        filtro = _alcance(db, u, unidad_id)
    trabs = db.scalars(select(Trabajador).where(filtro, Trabajador.activo).order_by(Trabajador.codigo)).all()
    hoy = date.today()
    out = []
    for t in trabs:
        movs = db.scalar(select(func.count(BancoHorasCompensatorias.id))
                         .where(BancoHorasCompensatorias.trabajador_id == t.id)) or 0
        if solo_con_movimientos and not movs:
            continue
        por_vencer = db.scalar(select(func.coalesce(func.sum(BancoHorasCompensatorias.horas), 0)).where(
            BancoHorasCompensatorias.trabajador_id == t.id, BancoHorasCompensatorias.tipo == "credito",
            BancoHorasCompensatorias.fecha_expira >= hoy,
            BancoHorasCompensatorias.fecha_expira <= hoy + timedelta(days=30)))
        out.append(_trab(t) | {"saldo_horas": _saldo(db, t.id), "movimientos": movs,
                                "creditos_por_vencer_30d": float(por_vencer or 0)})
    return out
