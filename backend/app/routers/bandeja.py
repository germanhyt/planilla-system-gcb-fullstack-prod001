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
from sqlalchemy import Date, Float, Integer, String, and_, cast, func, literal, null, select, true, union_all
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from ..alcance import filtro_empresa
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
from ..paginacion import filtrar_sql, paginar_sql, params_pagina
from ..reglas_sql import regla_sql
from ..rules import BASE, efectivas
from .reglas import vigente

LIMA = ZoneInfo("America/Lima")
router = APIRouter(prefix="/excepciones", tags=["excepciones"])
banco = APIRouter(prefix="/banco-horas", tags=["banco_horas"])

TIPOS = ("he_no_programada", "tardanza", "fuera_geocerca", "marca_diferida", "pt_alerta")
GESTORES = ("jefe", "rrhh", "admin")


def _alcance(db: Session, u: Usuario, unidad_id: Optional[int], empresa_id: Optional[int] = None):
    """Filtro de trabajadores según rol: jefe sólo su unidad; RRHH/admin todo (o la unidad pedida)."""
    if u.rol not in GESTORES:
        raise HTTPException(403, "No autorizado")
    if u.rol == "jefe":
        if not u.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        return and_(Trabajador.unidad_id == u.unidad_id, filtro_empresa(u, empresa_id))
    return and_(Trabajador.unidad_id == unidad_id if unidad_id else true(), filtro_empresa(u, empresa_id))


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


def _pt_semanas(db: Session, filtro, desde: date, hasta: date):
    """SELECT de semanas (lun-dom) que tocan [desde, hasta] con promedio PT85/PT102 > umbral vigente (en la BD)."""
    lunes = desde - timedelta(days=desde.weekday())
    fin = hasta - timedelta(days=hasta.weekday()) + timedelta(days=7)
    sem = cast(func.date_trunc("week", Asistencia.dia_operativo), Date)
    total = func.sum(cast(Asistencia.horas_trabajadas, Float))
    dias = func.count(Asistencia.id)
    umbral = regla_sql(db, Trabajador.empresa_id, sem, lambda r: float(r["part_time"]["alerta_promedio_diario_horas"]),
                       defecto=float(efectivas({})["part_time"]["alerta_promedio_diario_horas"]), antes_primera=True,
                       tipo=Float())
    return (select(Trabajador.id.label("trabajador_id"), TipoContrato.codigo.label("contrato"), sem.label("sem"),
                   total.label("total"), dias.label("dias"), umbral.label("umbral"))
            .join(Asistencia, Asistencia.trabajador_id == Trabajador.id)
            .join(TipoContrato, TipoContrato.id == Trabajador.tipo_contrato_id)
            .where(filtro, TipoContrato.codigo.in_(("PT85", "PT102")), Asistencia.dia_operativo >= lunes,
                   Asistencia.dia_operativo < fin, Asistencia.horas_trabajadas.isnot(None))
            .group_by(Trabajador.id, Trabajador.empresa_id, TipoContrato.codigo, sem)
            .having(total / dias > umbral))


def alertas_pt(db: Session, filtro, desde: date, hasta: date) -> list[dict]:
    """Semanas (lun-dom) que tocan [desde, hasta] donde un PT85/PT102 promedia > umbral h por día trabajado."""
    filas = db.execute(_pt_semanas(db, filtro, desde, hasta)).all()
    trabs = {t.id: t for t in db.scalars(select(Trabajador).where(Trabajador.id.in_({f.trabajador_id for f in filas})))}
    return [{"trabajador": trabs[f.trabajador_id], "contrato": f.contrato, "semana": f.sem,
             "promedio": round(f.total / f.dias, 2), "total": round(f.total, 2), "dias": f.dias, "umbral": f.umbral}
            for f in filas]


def _union_bandeja(db: Session, filtro, desde: date, hasta: date):
    """UNION ALL de las 5 fuentes con columnas comunes (en la BD, sin topes)."""
    dia_lima = cast(func.timezone("America/Lima", Marca.ts_servidor), Date)
    nulo_f, nulo_i, nulo_s = (null().cast(Float), null().cast(Integer), null().cast(String))

    def cols(clave, tipo, orden, ref, dia, estado, horas=nulo_f, n=nulo_i, contrato=nulo_s, umbral=nulo_f, tid=None):
        return (clave.label("clave"), literal(tipo).label("tipo"), literal(orden).label("orden"), ref.label("ref_id"),
                (tid if tid is not None else Trabajador.id).label("trabajador_id"), dia.label("dia"),
                estado.label("estado"), horas.label("horas"), n.label("n"), contrato.label("contrato"),
                umbral.label("umbral"))

    he = (select(*cols(literal("he-") + cast(RegularizacionHE.id, String), "he_no_programada", 0, RegularizacionHE.id,
                       Asistencia.dia_operativo, RegularizacionHE.estado, horas=cast(RegularizacionHE.horas_exceso, Float)))
          .join(Asistencia, Asistencia.id == RegularizacionHE.asistencia_id)
          .join(Trabajador, Trabajador.id == RegularizacionHE.trabajador_id)
          .where(filtro, Asistencia.dia_operativo >= desde, Asistencia.dia_operativo <= hasta))
    tar = (select(*cols(literal("tar-") + cast(Asistencia.id, String), "tardanza", 1, Asistencia.id,
                        Asistencia.dia_operativo, literal("informativo"), n=Asistencia.tardanza_min))
           .join(Trabajador, Trabajador.id == Asistencia.trabajador_id)
           .where(filtro, Asistencia.tardanza_min > 0, Asistencia.dia_operativo >= desde, Asistencia.dia_operativo <= hasta))
    geo = (select(*cols(literal("geo-") + cast(Marca.id, String), "fuera_geocerca", 2, Marca.id, dia_lima,
                        literal("informativo")))
           .join(Trabajador, Trabajador.id == Marca.trabajador_id)
           .where(filtro, Marca.validacion_estado == "fuera_geocerca", dia_lima >= desde, dia_lima <= hasta))
    umbral_dif = regla_sql(db, Trabajador.empresa_id, dia_lima,
                           lambda r: int(r["marcacion_offline"]["umbral_diferida_min"]),
                           defecto=int(BASE["marcacion_offline"]["umbral_diferida_min"]), tipo=Integer())
    dif = (select(*cols(literal("dif-") + cast(Marca.id, String), "marca_diferida", 3, Marca.id, dia_lima,
                        literal("informativo"), n=Marca.diferencia_min, umbral=cast(umbral_dif, Float)))
           .join(Trabajador, Trabajador.id == Marca.trabajador_id)
           .where(filtro, Marca.diferida.is_(True), Marca.diferencia_min.isnot(None), dia_lima >= desde,
                  dia_lima <= hasta, Marca.diferencia_min > umbral_dif))
    p = _pt_semanas(db, filtro, desde, hasta).subquery()
    pt = select(*cols(literal("pt-") + cast(p.c.trabajador_id, String) + literal("-") + cast(p.c.sem, String),
                      "pt_alerta", 4, nulo_i, p.c.sem, literal("informativo"), horas=p.c.total, n=p.c.dias,
                      contrato=p.c.contrato, umbral=p.c.umbral, tid=p.c.trabajador_id))
    return union_all(he, tar, geo, dif, pt).subquery("bandeja")


def _hidratar(db: Session, filas, filtro, desde: date, hasta: date) -> list[dict]:
    """Construye los ítems sólo de las filas de la página (consultas por lote)."""
    ids = lambda t: {f.ref_id for f in filas if f.tipo == t}  # noqa: E731
    he = {r.id: (r, a, e) for r, a, e in db.execute(
        select(RegularizacionHE, Asistencia, Empresa).join(Asistencia, Asistencia.id == RegularizacionHE.asistencia_id)
        .join(Trabajador, Trabajador.id == RegularizacionHE.trabajador_id).join(Empresa, Empresa.id == Trabajador.empresa_id)
        .where(RegularizacionHE.id.in_(ids("he_no_programada"))))} if ids("he_no_programada") else {}
    mids = ids("fuera_geocerca") | ids("marca_diferida")
    marcas = {m.id: m for m in db.scalars(select(Marca).where(Marca.id.in_(mids)))} if mids else {}
    trabs = {t.id: t for t in db.scalars(select(Trabajador).where(Trabajador.id.in_({f.trabajador_id for f in filas})))}
    alertas = {}
    he_trabs = {trabs[f.trabajador_id].id for f in filas if f.tipo == "he_no_programada"}
    if he_trabs:
        for a in alertas_pt(db, and_(filtro, Trabajador.id.in_(he_trabs)), desde, hasta):
            alertas[(a["trabajador"].id, a["semana"])] = a
    out = []
    for f in filas:
        t = trabs[f.trabajador_id]
        base = {"clave": f.clave, "tipo": f.tipo, "ref_id": f.ref_id, "trabajador": _trab(t), "dia": f.dia.isoformat(),
                "estado": f.estado, "accionable": False}
        if f.tipo == "he_no_programada":
            reg, asi, emp = he[f.ref_id]
            alerta = alertas.get((t.id, asi.dia_operativo - timedelta(days=asi.dia_operativo.weekday())))
            base |= {"empresa": emp.codigo, "detalle": f"{float(reg.horas_exceso):.2f} h de exceso no programado (no autorizado)",
                     "horas": float(reg.horas_exceso), "destino": reg.destino,
                     "destino_default": destino_default(db, t.empresa_id, asi.dia_operativo),
                     "observacion": reg.observacion, "accionable": reg.estado == "pendiente",
                     "alerta_pt": f"{alerta['contrato']}: promedio {alerta['promedio']} h/día en la semana" if alerta else None}
        elif f.tipo == "tardanza":
            base["detalle"] = f"Tardanza de {f.n} min"
        elif f.tipo == "fuera_geocerca":
            m = marcas[f.ref_id]
            dist = f" a {round(float(m.distancia_m))} m" if m.distancia_m is not None else ""
            base["detalle"] = f"Marca de {m.tipo} fuera de geocerca{dist}"
        elif f.tipo == "marca_diferida":
            m = marcas[f.ref_id]
            disp = m.ts_cliente.astimezone(LIMA).strftime("%d/%m %H:%M") if m.ts_cliente else "?"
            base["detalle"] = (f"Marca de {m.tipo} sincronizada offline {m.diferencia_min} min despues"
                               f" (dispositivo {disp}; umbral {int(f.umbral)} min). Revisar")
        else:
            prom, total = round(f.horas / f.n, 2), round(f.horas, 2)
            base["detalle"] = (f"{f.contrato}: promedio {prom} h/día ({total} h en {f.n} días)"
                               f" > {f.umbral:g} h/día. Alerta no bloqueante")
        out.append(base)
    return out


@router.get("/bandeja")
def bandeja(
    desde: date = Query(...),
    hasta: date = Query(...),
    tipo: Optional[Literal["he_no_programada", "tardanza", "fuera_geocerca", "marca_diferida", "pt_alerta"]] = None,
    estado: Optional[Literal["pendiente", "aprobado", "rechazado", "informativo"]] = None,
    unidad_id: Optional[int] = None,
    empresa_id: Optional[int] = None,
    db: Session = Depends(get_db),
    u: Usuario = Depends(current_user),
    pag: Optional[dict] = Depends(params_pagina),
):
    """Bandeja unificada de excepciones. Jefe: su unidad. RRHH/admin: todas. Trabajador: 403.

    S8 paso 7: UNION ALL de las fuentes en la BD; con ``?page=`` filtra (q/tipo/estado), cuenta, ordena y pagina en
    SQL e hidrata sólo la página; ``resumen`` trae los KPI (total/pendientes/fuera_geocerca) con los mismos filtros.
    Sin ``page`` devuelve la lista completa (misma consulta, sin topes)."""
    filtro = _alcance(db, u, unidad_id, empresa_id)
    if hasta < desde:
        raise HTTPException(400, "Rango inválido")
    b = _union_bandeja(db, filtro, desde, hasta)
    params = {"tipo": tipo, "estado": estado, **{k: v for k, v in (pag or {}).items() if k in ("q", "sort", "page", "page_size")}}
    stmt = select(b).join(Trabajador, Trabajador.id == b.c.trabajador_id)
    kw = dict(buscar=(Trabajador.codigo, Trabajador.nombres, Trabajador.apellidos, b.c.tipo),
              filtros={"tipo": b.c.tipo, "estado": b.c.estado},
              orden={"dia": b.c.dia, "tipo": b.c.tipo, "estado": b.c.estado, "trabajador": Trabajador.codigo,
                     "trabajador.codigo": Trabajador.codigo},
              orden_def=(b.c.dia.desc(), b.c.orden), desempate=(b.c.ref_id.desc().nulls_last(), b.c.clave))
    res = paginar_sql(db, stmt, params, lambda r: r, sin_limite=pag is None, **kw)
    res["items"] = _hidratar(db, res["items"], filtro, desde, hasta)
    if pag is None:
        return res["items"]
    f = filtrar_sql(stmt, params, buscar=kw["buscar"], filtros=kw["filtros"]).subquery()
    tot, pend, geo = db.execute(select(func.count(), func.count().filter(f.c.estado == "pendiente"),
                                       func.count().filter(f.c.tipo == "fuera_geocerca")).select_from(f)).one()
    res["resumen"] = {"total": tot, "pendientes": pend, "fuera_geocerca": geo}
    return res


def _saldo(db: Session, trabajador_id: int) -> float:
    ult = db.scalar(select(BancoHorasCompensatorias.saldo_nuevo)
                    .where(BancoHorasCompensatorias.trabajador_id == trabajador_id)
                    .order_by(BancoHorasCompensatorias.creado_en.desc(), BancoHorasCompensatorias.id.desc()).limit(1))
    return float(ult) if ult is not None else 0.0


@banco.get("/saldos")
def saldos(unidad_id: Optional[int] = None, empresa_id: Optional[int] = None, solo_con_movimientos: bool = False, db: Session = Depends(get_db),
           u: Usuario = Depends(current_user), pag: Optional[dict] = Depends(params_pagina)):
    """Saldo de la bolsa de horas por trabajador. Trabajador: sólo el suyo; jefe: su unidad; RRHH/admin: todos.

    S8 paso 7: saldo, movimientos y créditos por vencer como subconsultas correlacionadas; filtro, orden y
    LIMIT/OFFSET en la BD con ``?page=`` (sin ``page``: la lista completa como antes)."""
    if u.rol == "trabajador":
        filtro = Trabajador.usuario_id == u.id
    else:
        filtro = _alcance(db, u, unidad_id, empresa_id)
    B = BancoHorasCompensatorias
    hoy = date.today()
    movs = select(func.count(B.id)).where(B.trabajador_id == Trabajador.id).correlate(Trabajador).scalar_subquery()
    saldo = func.coalesce(select(B.saldo_nuevo).where(B.trabajador_id == Trabajador.id).correlate(Trabajador)
                          .order_by(B.creado_en.desc(), B.id.desc()).limit(1).scalar_subquery(), 0)
    pv = select(func.coalesce(func.sum(B.horas), 0)).where(
        B.trabajador_id == Trabajador.id, B.tipo == "credito", B.fecha_expira >= hoy,
        B.fecha_expira <= hoy + timedelta(days=30)).correlate(Trabajador).scalar_subquery()
    stmt = select(Trabajador, saldo.label("saldo"), movs.label("movs"), pv.label("pv")).where(filtro, Trabajador.activo)
    if solo_con_movimientos:
        stmt = stmt.where(movs > 0)

    def fila(r):
        t, s_, m_, p_ = r
        return _trab(t) | {"saldo_horas": float(s_ or 0), "movimientos": m_ or 0, "creditos_por_vencer_30d": float(p_ or 0)}

    res = paginar_sql(db, stmt, pag or {}, fila, buscar=(Trabajador.codigo, Trabajador.nombres, Trabajador.apellidos),
                      orden={"codigo": Trabajador.codigo, "nombre": Trabajador.nombres, "saldo_horas": saldo,
                             "movimientos": movs, "creditos_por_vencer_30d": pv},
                      orden_def=(Trabajador.codigo,), desempate=(Trabajador.id,), sin_limite=pag is None)
    return res if pag is not None else res["items"]
