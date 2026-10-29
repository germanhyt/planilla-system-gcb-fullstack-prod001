from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import audit, to_dict
from ..db import get_db
from ..deps import require
from ..models import Empresa, RuleSet, Usuario
from ..rules import BASE, efectivas
from ..schemas import RuleSetIn

r = APIRouter(prefix="/rule-sets", tags=["reglas"])
LECTURA = ("jefe", "rrhh", "admin")


def vigente(db: Session, empresa_id: int, fecha: date) -> Optional[RuleSet]:
    return db.scalar(select(RuleSet).where(RuleSet.empresa_id == empresa_id, RuleSet.valid_from <= fecha)
                     .order_by(RuleSet.valid_from.desc()).limit(1))


@r.get("/base")
def base(_: Usuario = Depends(require(*LECTURA))):
    return BASE


@r.get("")
def listar(empresa_id: Optional[int] = None, db: Session = Depends(get_db), _: Usuario = Depends(require(*LECTURA))):
    q = select(RuleSet).order_by(RuleSet.empresa_id, RuleSet.version)
    if empresa_id:
        q = q.where(RuleSet.empresa_id == empresa_id)
    return [to_dict(x) for x in db.scalars(q)]


@r.get("/vigente")
def obtener_vigente(empresa_id: int, fecha: date, db: Session = Depends(get_db), _: Usuario = Depends(require(*LECTURA))):
    rs = vigente(db, empresa_id, fecha)
    if not rs:
        raise HTTPException(404, "Sin reglas vigentes para esa fecha")
    return {"rule_set_id": rs.id, "version": rs.version, "valid_from": rs.valid_from.isoformat(),
            "overrides": rs.config, "efectivas": efectivas(rs.config)}


@r.post("", status_code=201)
def crear(body: RuleSetIn, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(require("admin"))):
    """Nueva versión (inmutable). No existe PUT/DELETE: corregir = publicar otra versión."""
    if not db.get(Empresa, body.empresa_id):
        raise HTTPException(404, "Empresa no existe")
    try:
        efectivas(body.config)
    except ValidationError as e:
        raise HTTPException(422, f"Configuración inválida: {e.errors(include_url=False)}") from e
    if db.scalar(select(RuleSet).where(RuleSet.empresa_id == body.empresa_id, RuleSet.valid_from == body.valid_from)):
        raise HTTPException(409, "Ya existe una versión con esa vigencia")
    ver = (db.scalar(select(func.max(RuleSet.version)).where(RuleSet.empresa_id == body.empresa_id)) or 0) + 1
    rs = RuleSet(empresa_id=body.empresa_id, version=ver, valid_from=body.valid_from, config=body.config,
                 motivo=body.motivo, creado_por=u.id)
    db.add(rs)
    db.flush()
    audit(db, u.id, "crear", "rule_set", rs.id, None, to_dict(rs), request.client.host if request.client else None)
    db.commit()
    return to_dict(rs)
