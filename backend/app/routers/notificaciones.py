"""Sprint 7: notificaciones internas para RRHH/admin (sin correo)."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..alcance import empresa_alcance
from ..alertas import generar
from ..audit import audit
from ..db import get_db
from ..deps import current_user
from ..models import Empresa, Notificacion, Usuario

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])
PERIODO = r"^\d{4}-(0[1-9]|1[0-2])$"


def _gestor(user: Usuario):
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")


def _out(n: Notificacion) -> dict:
    return {"id": n.id, "empresa_id": n.empresa_id, "periodo": n.periodo, "tipo": n.tipo, "mensaje": n.mensaje,
            "datos": n.datos, "activa": n.activa, "leida": n.leida_en is not None,
            "creada_en": n.creada_en.isoformat() if n.creada_en else None}


def _q(db: Session, user: Usuario, empresa_id: Optional[int]):
    eid = empresa_alcance(user, empresa_id)
    q = db.query(Notificacion)
    return q.filter(Notificacion.empresa_id == eid) if eid else q


@router.get("")
def listar(empresa_id: Optional[int] = None, periodo: Optional[str] = Query(None, pattern=PERIODO),
           solo_activas: bool = True, solo_no_leidas: bool = False,
           db: Session = Depends(get_db), user: Usuario = Depends(current_user)):
    _gestor(user)
    q = _q(db, user, empresa_id)
    if periodo:
        q = q.filter(Notificacion.periodo == periodo)
    if solo_activas:
        q = q.filter(Notificacion.activa.is_(True))
    if solo_no_leidas:
        q = q.filter(Notificacion.leida_en.is_(None))
    return [_out(n) for n in q.order_by(Notificacion.id.desc()).limit(500)]


@router.get("/conteo")
def conteo(empresa_id: Optional[int] = None, db: Session = Depends(get_db), user: Usuario = Depends(current_user)):
    _gestor(user)
    return {"no_leidas": _q(db, user, empresa_id).filter(Notificacion.activa.is_(True),
                                                         Notificacion.leida_en.is_(None)).count()}


@router.post("/generar")
def generar_alertas(periodo: str = Query(..., pattern=PERIODO), empresa_id: Optional[int] = None,
                    db: Session = Depends(get_db), user: Usuario = Depends(current_user)):
    """(Re)evalua las alertas del periodo para las empresas del alcance. Idempotente."""
    _gestor(user)
    eid = empresa_alcance(user, empresa_id)
    empresas = [eid] if eid else [e.id for e in db.query(Empresa).order_by(Empresa.id)]
    res = {str(e): generar(db, e, periodo) for e in empresas}
    db.commit()
    return {"periodo": periodo, "activas_por_empresa": res}


@router.post("/{nid}/leida")
def marcar_leida(nid: int, db: Session = Depends(get_db), user: Usuario = Depends(current_user)):
    _gestor(user)
    n = db.get(Notificacion, nid)
    if not n:
        raise HTTPException(404, "Notificacion no encontrada")
    empresa_alcance(user, n.empresa_id)
    if n.leida_en is None:
        n.leida_por, n.leida_en = user.id, datetime.now(timezone.utc)
        audit(db, user.id, "leer", "notificacion", n.id, None, {"tipo": n.tipo, "clave": n.clave})
        db.commit()
    return _out(n)
