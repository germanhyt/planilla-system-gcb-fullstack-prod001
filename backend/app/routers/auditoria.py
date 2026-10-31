from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import to_dict
from ..db import get_db
from ..deps import require
from ..models import Auditoria, Usuario

r = APIRouter(prefix="/auditoria", tags=["auditoria"])


@r.get("")
def listar(entidad: Optional[str] = None, accion: Optional[str] = None, entidad_id: Optional[str] = None, limit: int = 200,
           db: Session = Depends(get_db), _: Usuario = Depends(require("rrhh", "admin"))):
    q = select(Auditoria).order_by(Auditoria.id.desc()).limit(min(limit, 1000))
    if entidad:
        q = q.where(Auditoria.entidad == entidad)
    if accion:
        q = q.where(Auditoria.accion == accion)
    if entidad_id:
        q = q.where(Auditoria.entidad_id == entidad_id)
    return [to_dict(a) for a in db.scalars(q)]
