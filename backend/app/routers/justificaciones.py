"""Sprint 4: justificación real de faltas.

- Trabajador: solicita para sí mismo (estado pendiente) y puede retirar su solicitud mientras esté pendiente.
- Jefe (su unidad) / RRHH / admin: aprueban o rechazan; si registran ellos mismos queda aprobada.
- Sin duplicados: una justificación viva (pendiente o aprobada) por trabajador y día -> 409.
- Bloqueo 409 si el periodo del día está cerrado.
"""
from datetime import date, datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import audit, to_dict
from ..cierre import exigir_abierto_trabajador
from ..db import get_db
from ..deps import current_user, require
from ..models import FaltaJustificada, Trabajador, Usuario
from ..schemas import FaltaJustificadaIn

r = APIRouter(prefix="/justificaciones", tags=["justificaciones"])


class DecisionIn(BaseModel):
    aprobar: bool
    comentario: Optional[str] = Field(None, max_length=500)


def _trab(db: Session, u: Usuario, trabajador_id: int) -> Trabajador:
    t = db.get(Trabajador, trabajador_id)
    if not t:
        raise HTTPException(404, "Trabajador no encontrado")
    if u.rol == "jefe" and t.unidad_id != u.unidad_id:
        raise HTTPException(403, "Solo trabajadores de su unidad")
    if u.rol == "trabajador" and t.usuario_id != u.id:
        raise HTTPException(403, "Solo puede justificar sus propias faltas")
    return t


def out(f: FaltaJustificada, t: Optional[Trabajador] = None) -> dict:
    d = {"id": f.id, "trabajador_id": f.trabajador_id, "dia": f.dia.isoformat(), "motivo": f.motivo,
         "descripcion": f.descripcion, "adjunto_url": f.adjunto_url, "estado": f.estado,
         "solicitado_por": f.solicitado_por, "decidido_por": f.justificado_por,
         "decidido_en": f.decidido_en.isoformat() if f.decidido_en else None, "comentario_decision": f.comentario_decision}
    if t:
        d["trabajador"] = {"codigo": t.codigo, "nombres": t.nombres, "apellidos": t.apellidos}
    return d


def registrar(db: Session, u: Usuario, data: FaltaJustificadaIn) -> FaltaJustificada:
    t = _trab(db, u, data.trabajador_id)
    exigir_abierto_trabajador(db, t.id, data.dia.strftime("%Y-%m"))
    viva = db.query(FaltaJustificada).filter(FaltaJustificada.trabajador_id == t.id, FaltaJustificada.dia == data.dia,
                                             FaltaJustificada.estado != "rechazada").first()
    if viva:
        raise HTTPException(409, f"Ya existe una justificación {viva.estado} para ese día")
    gestor = u.rol in ("jefe", "rrhh", "admin")
    f = FaltaJustificada(trabajador_id=t.id, dia=data.dia, motivo=data.motivo, descripcion=data.descripcion,
                         adjunto_url=data.adjunto_url, solicitado_por=u.id,
                         estado="aprobada" if gestor else "pendiente",
                         justificado_por=u.id if gestor else None,
                         decidido_en=datetime.now(timezone.utc) if gestor else None)
    db.add(f)
    try:
        db.flush()
    except IntegrityError:  # carrera: el índice único parcial también protege
        db.rollback()
        raise HTTPException(409, "Ya existe una justificación para ese día") from None
    audit(db, u.id, "crear", "falta_justificada", f.id, None, to_dict(f))
    db.commit()
    return f


@r.post("", status_code=201)
def crear(data: FaltaJustificadaIn, db: Session = Depends(get_db), u: Usuario = Depends(current_user)):
    return out(registrar(db, u, data))


@r.get("")
def listar(desde: Optional[date] = None, hasta: Optional[date] = None,
           estado: Optional[Literal["pendiente", "aprobada", "rechazada"]] = None,
           db: Session = Depends(get_db), u: Usuario = Depends(current_user)):
    q = db.query(FaltaJustificada, Trabajador).join(Trabajador, Trabajador.id == FaltaJustificada.trabajador_id)
    if u.rol == "jefe":
        q = q.filter(Trabajador.unidad_id == u.unidad_id)
    elif u.rol == "trabajador":
        q = q.filter(Trabajador.usuario_id == u.id)
    if desde:
        q = q.filter(FaltaJustificada.dia >= desde)
    if hasta:
        q = q.filter(FaltaJustificada.dia <= hasta)
    if estado:
        q = q.filter(FaltaJustificada.estado == estado)
    return [out(f, t) for f, t in q.order_by(FaltaJustificada.dia.desc(), FaltaJustificada.id.desc())]


@r.post("/{fid}/decidir")
def decidir(fid: int, body: DecisionIn, db: Session = Depends(get_db), u: Usuario = Depends(require("jefe", "rrhh", "admin"))):
    f = db.get(FaltaJustificada, fid)
    if not f:
        raise HTTPException(404, "Justificación no encontrada")
    _trab(db, u, f.trabajador_id)
    if f.estado != "pendiente":
        raise HTTPException(409, f"La justificación ya está {f.estado}")
    exigir_abierto_trabajador(db, f.trabajador_id, f.dia.strftime("%Y-%m"))
    antes = to_dict(f)
    f.estado = "aprobada" if body.aprobar else "rechazada"
    f.justificado_por, f.decidido_en, f.comentario_decision = u.id, datetime.now(timezone.utc), body.comentario
    audit(db, u.id, "aprobar" if body.aprobar else "rechazar", "falta_justificada", f.id, antes, to_dict(f))
    db.commit()
    return out(f)


@r.delete("/{fid}")
def retirar(fid: int, db: Session = Depends(get_db), u: Usuario = Depends(current_user)):
    f = db.get(FaltaJustificada, fid)
    if not f:
        raise HTTPException(404, "Justificación no encontrada")
    _trab(db, u, f.trabajador_id)
    if f.estado != "pendiente":
        raise HTTPException(409, "Solo se puede retirar una solicitud pendiente")
    exigir_abierto_trabajador(db, f.trabajador_id, f.dia.strftime("%Y-%m"))
    audit(db, u.id, "retirar", "falta_justificada", f.id, to_dict(f), None)
    db.delete(f)
    db.commit()
    return {"ok": True}
