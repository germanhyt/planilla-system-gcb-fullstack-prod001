from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit, to_dict
from ..db import get_db
from ..deps import require
from ..models import BonoNocturno, BonoNocturnoHistorial, Trabajador, Usuario
from ..schemas import BonoDecision, BonoIn

r = APIRouter(prefix="/bonos-nocturnos", tags=["bono nocturno 3 AM"])


def _ip(req):
    return req.client.host if req.client else None


@r.get("")
def listar(periodo: Optional[str] = None, db: Session = Depends(get_db), _: Usuario = Depends(require("rrhh", "admin"))):
    q = select(BonoNocturno).order_by(BonoNocturno.id)
    if periodo:
        q = q.where(BonoNocturno.periodo == periodo)
    return [to_dict(b) for b in db.scalars(q)]


@r.post("", status_code=201)
def registrar(body: BonoIn, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(require("admin"))):
    """Registra o corrige (vuelve a 'registrado') el bono de un trabajador en un periodo."""
    if not db.get(Trabajador, body.trabajador_id):
        raise HTTPException(404, "Trabajador no existe")
    b = db.scalar(select(BonoNocturno).where(BonoNocturno.trabajador_id == body.trabajador_id,
                                             BonoNocturno.periodo == body.periodo))
    antes = to_dict(b) if b else None
    if b:
        b.cantidad, b.observacion, b.estado, b.registrado_por, b.aprobado_por = body.cantidad, body.observacion, "registrado", u.id, None
        accion = "corregir"
    else:
        b = BonoNocturno(**body.model_dump(), registrado_por=u.id, estado="registrado")
        db.add(b)
        accion = "registrar"
    db.flush()
    db.add(BonoNocturnoHistorial(bono_id=b.id, usuario_id=u.id, accion=accion, cantidad=b.cantidad, estado=b.estado,
                                 comentario=body.observacion))
    audit(db, u.id, "crear" if not antes else "actualizar", "bono_nocturno", b.id, antes, to_dict(b), _ip(request))
    db.commit()
    return to_dict(b)


@r.post("/{bid}/decision")
def decidir(bid: int, body: BonoDecision, request: Request, db: Session = Depends(get_db),
            u: Usuario = Depends(require("rrhh", "admin"))):
    b = db.get(BonoNocturno, bid)
    if not b:
        raise HTTPException(404, "Bono no existe")
    if b.estado != "registrado":
        raise HTTPException(409, f"El bono ya está {b.estado}")
    if b.registrado_por == u.id:
        raise HTTPException(403, "Quien registra no puede aprobar (segregación de funciones)")
    antes = to_dict(b)
    b.estado = "aprobado" if body.aprobar else "rechazado"
    b.aprobado_por = u.id
    db.add(BonoNocturnoHistorial(bono_id=b.id, usuario_id=u.id, accion=b.estado, cantidad=b.cantidad, estado=b.estado,
                                 comentario=body.comentario))
    audit(db, u.id, "aprobar" if body.aprobar else "rechazar", "bono_nocturno", b.id, antes, to_dict(b), _ip(request))
    db.commit()
    return to_dict(b)


@r.get("/{bid}/historial")
def historial(bid: int, db: Session = Depends(get_db), _: Usuario = Depends(require("rrhh", "admin"))):
    return [to_dict(h) for h in db.scalars(select(BonoNocturnoHistorial).where(BonoNocturnoHistorial.bono_id == bid)
                                           .order_by(BonoNocturnoHistorial.id))]
