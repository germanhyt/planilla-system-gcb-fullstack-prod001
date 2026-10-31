"""Sprint 3: cierre y reapertura de periodos (mes calendario por día operativo).

- GET  /periodos/checklist: pendientes previos (HE sin decidir, excepciones, marcas incompletas, bonos sin aprobar).
- POST /periodos/cerrar: RRHH/admin. Con pendientes exige `confirmar=true` (si no, 409 con el checklist).
  Al cerrar se bloquean marcas, regularizaciones y bonos del periodo (409) y la exportación pasa a FINAL.
- POST /periodos/reabrir/{id}: sólo admin, con motivo; queda en auditoría.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..alcance import empresa_alcance
from ..audit import audit
from ..banco import acreditar_he_programadas
from ..cierre import checklist
from ..db import get_db
from ..deps import current_user
from ..models import Asistencia, CierrePeriodo, Empresa, Trabajador, Usuario
from ..paginacion import paginar_sql, params_pagina
from ..schemas import CierrePeriodoIn, ReaperturaPeriodoIn

router = APIRouter(prefix="/periodos", tags=["periodos"])
PERIODO = r"^\d{4}-(0[1-9]|1[0-2])$"


def _ip(req):
    return req.client.host if req.client else None


def _gestor(user: Usuario):
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")


def _marcar_asistencias(db: Session, empresa_id: int, periodo: str, cerrado: bool):
    tids = db.query(Trabajador.id).filter(Trabajador.empresa_id == empresa_id).subquery()
    db.query(Asistencia).filter(Asistencia.periodo == periodo, Asistencia.trabajador_id.in_(tids)) \
        .update({Asistencia.periodo_cerrado: cerrado}, synchronize_session=False)


def _out(c: CierrePeriodo) -> dict:
    return {"id": c.id, "empresa_id": c.empresa_id, "periodo": c.periodo, "estado": c.estado,
            "cerrado_por": c.cerrado_por, "cerrado_en": c.cerrado_en.isoformat() if c.cerrado_en else None,
            "reabierto_por": c.reabierto_por, "reabierto_en": c.reabierto_en.isoformat() if c.reabierto_en else None,
            "razon_reapertura": c.razon_reapertura}


@router.get("/checklist")
def ver_checklist(empresa_id: int = Query(...), periodo: str = Query(..., pattern=PERIODO),
                  db: Session = Depends(get_db), user: Usuario = Depends(current_user)):
    _gestor(user)
    empresa_alcance(user, empresa_id)
    if not db.get(Empresa, empresa_id):
        raise HTTPException(404, "Empresa no encontrada")
    out = checklist(db, empresa_id, periodo)
    c = db.query(CierrePeriodo).filter(CierrePeriodo.empresa_id == empresa_id, CierrePeriodo.periodo == periodo).first()
    out["cierre"] = _out(c) if c else None
    return out


@router.post("/cerrar")
def cerrar_periodo(data: CierrePeriodoIn, request: Request, db: Session = Depends(get_db),
                   user: Usuario = Depends(current_user)):
    """Cierra el mes operativo de una empresa. Con pendientes exige confirmación explícita."""
    _gestor(user)
    empresa_alcance(user, data.empresa_id)
    if not db.get(Empresa, data.empresa_id):
        raise HTTPException(404, "Empresa no encontrada")
    cierre = db.query(CierrePeriodo).filter(CierrePeriodo.empresa_id == data.empresa_id,
                                            CierrePeriodo.periodo == data.periodo).first()
    if cierre and cierre.estado == "cerrado":
        raise HTTPException(400, f"Periodo {data.periodo} ya está cerrado para empresa {data.empresa_id}")
    chk = checklist(db, data.empresa_id, data.periodo)
    if chk["total_pendientes"] and not data.confirmar:
        raise HTTPException(409, {"mensaje": f"Hay {chk['total_pendientes']} pendientes; revise el checklist y confirme",
                                  "conteos": chk["conteos"]})
    antes = _out(cierre) if cierre else None
    if cierre:  # re-cierre tras una reapertura: se reutiliza la fila (único empresa+periodo), el historial queda en auditoría
        cierre.estado, cierre.cerrado_por, cierre.cerrado_en = "cerrado", user.id, datetime.now(timezone.utc)
    else:
        cierre = CierrePeriodo(empresa_id=data.empresa_id, periodo=data.periodo, cerrado_por=user.id, estado="cerrado")
        db.add(cierre)
    _marcar_asistencias(db, data.empresa_id, data.periodo, True)
    db.flush()
    acreditadas = acreditar_he_programadas(db, data.empresa_id, data.periodo)
    audit(db, user.id, "cerrar_periodo", "cierre_periodo", cierre.id, antes,
          {"periodo": data.periodo, "empresa_id": data.empresa_id, "confirmado_con_pendientes": bool(chk["total_pendientes"]),
           "pendientes": chk["conteos"], "he_programadas_al_banco": acreditadas}, _ip(request))
    db.commit()
    db.refresh(cierre)
    return _out(cierre) | {"pendientes": chk["conteos"]}


@router.post("/reabrir/{cierre_id}")
def reabrir_periodo(cierre_id: int, data: ReaperturaPeriodoIn, request: Request, db: Session = Depends(get_db),
                    user: Usuario = Depends(current_user)):
    """Reabre un periodo cerrado. Sólo admin, con motivo (mín. 10 caracteres) auditado."""
    if user.rol != "admin":
        raise HTTPException(403, "Solo admin puede reabrir periodos")
    cierre = db.get(CierrePeriodo, cierre_id)
    if not cierre:
        raise HTTPException(404, "Cierre no encontrado")
    empresa_alcance(user, cierre.empresa_id)
    if cierre.estado != "cerrado":
        raise HTTPException(400, "El periodo ya está reabierto")
    antes = _out(cierre)
    cierre.estado, cierre.reabierto_por = "reabierto", user.id
    cierre.reabierto_en, cierre.razon_reapertura = datetime.now(timezone.utc), data.razon_reapertura
    _marcar_asistencias(db, cierre.empresa_id, cierre.periodo, False)
    audit(db, user.id, "reabrir_periodo", "cierre_periodo", cierre.id, antes,
          {"estado": "reabierto", "razon": data.razon_reapertura, "periodo": cierre.periodo,
           "empresa_id": cierre.empresa_id}, _ip(request))
    db.commit()
    db.refresh(cierre)
    return _out(cierre)


@router.get("/historial")
def historial_cierres(empresa_id: Optional[int] = None, db: Session = Depends(get_db),
                      user: Usuario = Depends(current_user), pag: Optional[dict] = Depends(params_pagina)):
    """Estado actual de cierres por empresa+periodo (el detalle de cada cierre/reapertura está en auditoría).
    S9: ``?page=`` pagina, filtra (``estado``, ``q``) y ordena en la BD."""
    _gestor(user)
    empresa_id = empresa_alcance(user, empresa_id)
    if pag is not None:
        C = CierrePeriodo
        stmt = select(C).where(C.empresa_id == empresa_id) if empresa_id else select(C)
        return paginar_sql(db, stmt, pag, _out, escalar=True, buscar=(C.periodo, C.estado, C.razon_reapertura),
                           filtros={"estado": C.estado},
                           orden={"periodo": C.periodo, "estado": C.estado, "cerrado_en": C.cerrado_en,
                                  "reabierto_en": C.reabierto_en},
                           orden_def=(C.periodo.desc(),), desempate=(C.id.desc(),))
    q = db.query(CierrePeriodo)
    if empresa_id:
        q = q.filter(CierrePeriodo.empresa_id == empresa_id)
    return [_out(c) for c in q.order_by(CierrePeriodo.periodo.desc(), CierrePeriodo.id.desc()).all()]

@router.post("/recalcular")
def recalcular(empresa_id: int = Query(...), periodo: str = Query(..., pattern=PERIODO),
               trabajador_id: Optional[int] = None, db: Session = Depends(get_db),
               user: Usuario = Depends(current_user)):
    """Recalcula asistencias del periodo (todos los trabajadores activos o uno). Conserva las
    regularizaciones ya decididas; 409 si el periodo está cerrado."""
    from ..cierre import exigir_abierto
    from ..config import settings
    from ..engine import recalcular_trabajador_periodo
    _gestor(user)
    empresa_alcance(user, empresa_id)
    if not db.get(Empresa, empresa_id):
        raise HTTPException(404, "Empresa no encontrada")
    exigir_abierto(db, empresa_id, periodo)
    q = db.query(Trabajador.id).filter(Trabajador.empresa_id == empresa_id)
    if trabajador_id is not None:
        q = q.filter(Trabajador.id == trabajador_id)
    tids = [t for (t,) in q]
    if len(tids) > settings.jobs_umbral_sync:
        # Sprint 7: recalculos grandes -> trabajo RQ con progreso (GET /trabajos/{id}).
        from .. import trabajos
        t = trabajos.crear(db, "recalcular", {"empresa_id": empresa_id, "periodo": periodo, "trabajadores": tids},
                           user.id, empresa_id, total=len(tids))
        modo = trabajos.encolar(t.id)
        db.expire_all()
        tr = trabajos.out(db.get(type(t), t.id))
        return {"periodo": periodo, "trabajo": tr | {"modo": modo},
                "trabajadores_recalculados": (tr["resultado"] or {}).get("trabajadores_recalculados")}
    hechos = sum(1 for tid in tids if recalcular_trabajador_periodo(db, tid, periodo))
    audit(db, user.id, "recalcular", "periodo", empresa_id, None, {"periodo": periodo, "trabajadores": hechos})
    db.commit()
    return {"periodo": periodo, "trabajadores_recalculados": hechos, "trabajo": None}
