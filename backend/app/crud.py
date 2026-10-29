"""Fábrica de routers CRUD con RBAC + auditoría (soft delete vía 'activo')."""
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audit import audit, to_dict
from .db import get_db
from .deps import require
from .models import Usuario


def crud_router(model, prefix: str, entidad: str, create_schema: type[BaseModel], read_roles, write_roles,
                scope: Optional[Callable] = None) -> APIRouter:
    r = APIRouter(prefix=prefix, tags=[entidad])
    update_schema = create_schema

    def _get(db, id_, u):
        obj = db.get(model, id_)
        if not obj or (scope and db.scalar(scope(select(model).where(model.id == id_), u)) is None):
            raise HTTPException(404, f"{entidad} no encontrado")
        return obj

    def _commit(db):
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(409, f"Conflicto de datos: {e.orig.__class__.__name__}") from e

    @r.get("")
    def listar(incluir_inactivos: bool = False, db: Session = Depends(get_db), u: Usuario = Depends(require(*read_roles))):
        q = select(model).order_by(model.id)
        if not incluir_inactivos:
            q = q.where(model.activo.is_(True))
        if scope:
            q = scope(q, u)
        return [to_dict(o) for o in db.scalars(q)]

    @r.get("/{id_}")
    def obtener(id_: int, db: Session = Depends(get_db), u: Usuario = Depends(require(*read_roles))):
        return to_dict(_get(db, id_, u))

    @r.post("", status_code=201)
    def crear(body: create_schema, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(require(*write_roles))):
        obj = model(**body.model_dump())
        db.add(obj)
        _commit(db)
        audit(db, u.id, "crear", entidad, obj.id, None, to_dict(obj), request.client.host if request.client else None)
        db.commit()
        return to_dict(obj)

    @r.put("/{id_}")
    def actualizar(id_: int, body: update_schema, request: Request, db: Session = Depends(get_db),
                   u: Usuario = Depends(require(*write_roles))):
        obj = _get(db, id_, u)
        antes = to_dict(obj)
        for k, v in body.model_dump().items():
            setattr(obj, k, v)
        audit(db, u.id, "actualizar", entidad, obj.id, antes, to_dict(obj), request.client.host if request.client else None)
        _commit(db)
        return to_dict(obj)

    @r.delete("/{id_}")
    def eliminar(id_: int, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(require(*write_roles))):
        obj = _get(db, id_, u)
        antes = to_dict(obj)
        obj.activo = False
        audit(db, u.id, "eliminar", entidad, obj.id, antes, to_dict(obj), request.client.host if request.client else None)
        _commit(db)
        return {"ok": True}

    return r
