"""Sprint 4: programación de horas extra por el jefe (HE preautorizadas).

- Jefe: sólo trabajadores de su unidad. RRHH/admin: todos. Trabajador: consulta las suyas.
- Una programación vigente por trabajador y día operativo (POST hace upsert; DELETE la anula).
- Bloqueo 409 si el periodo (mes del día operativo) está cerrado.
- El motor usa estas horas como `he_programadas`: el exceso hasta ese tope se paga (25%/35%) y
  el resto llega a la bandeja del jefe como HE no programada (no autorizada).
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit import audit, to_dict
from ..cierre import exigir_abierto_trabajador
from ..db import get_db
from ..deps import current_user, require
from ..engine import he_programadas_dia  # noqa: F401 - re-export para consumidores
from ..models import HEProgramada, Trabajador, Usuario

r = APIRouter(prefix="/he-programadas", tags=["he_programadas"])


class HEProgramadaIn(BaseModel):
    trabajador_id: int
    dia: date
    horas: float = Field(gt=0, le=12)
    motivo: Optional[str] = Field(None, max_length=500)


def _out(h: HEProgramada, t: Optional[Trabajador] = None) -> dict:
    d = {"id": h.id, "trabajador_id": h.trabajador_id, "dia": h.dia.isoformat(), "horas": float(h.horas),
         "motivo": h.motivo, "estado": h.estado, "creado_por": h.creado_por}
    if t:
        d["trabajador"] = {"codigo": t.codigo, "nombres": t.nombres, "apellidos": t.apellidos}
    return d


def _alcance(u: Usuario, t: Trabajador) -> None:
    if u.rol == "jefe" and t.unidad_id != u.unidad_id:
        raise HTTPException(403, "Solo puede programar trabajadores de su unidad")
    if u.rol == "trabajador" and t.usuario_id != u.id:
        raise HTTPException(403, "Solo puede ver sus propias horas extra programadas")


@r.get("")
def listar(desde: date = Query(...), hasta: date = Query(...), trabajador_id: Optional[int] = None,
           incluir_anuladas: bool = False, db: Session = Depends(get_db), u: Usuario = Depends(current_user)):
    q = db.query(HEProgramada, Trabajador).join(Trabajador, Trabajador.id == HEProgramada.trabajador_id) \
        .filter(HEProgramada.dia >= desde, HEProgramada.dia <= hasta)
    if not incluir_anuladas:
        q = q.filter(HEProgramada.estado == "vigente")
    if trabajador_id:
        q = q.filter(HEProgramada.trabajador_id == trabajador_id)
    if u.rol == "jefe":
        if not u.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        q = q.filter(Trabajador.unidad_id == u.unidad_id)
    elif u.rol == "trabajador":
        q = q.filter(Trabajador.usuario_id == u.id)
    return [_out(h, t) for h, t in q.order_by(HEProgramada.dia, Trabajador.codigo).limit(1000)]


@r.post("")
def programar(data: HEProgramadaIn, db: Session = Depends(get_db), u: Usuario = Depends(require("jefe", "rrhh", "admin"))):
    t = db.get(Trabajador, data.trabajador_id)
    if not t:
        raise HTTPException(404, "Trabajador no encontrado")
    _alcance(u, t)
    exigir_abierto_trabajador(db, t.id, data.dia.strftime("%Y-%m"))
    h = db.query(HEProgramada).filter(HEProgramada.trabajador_id == t.id, HEProgramada.dia == data.dia).first()
    antes = to_dict(h) if h else None
    if h:
        h.horas, h.motivo, h.estado = Decimal(str(data.horas)), data.motivo, "vigente"
        h.creado_por, h.actualizado_en = u.id, datetime.now(timezone.utc)
    else:
        h = HEProgramada(trabajador_id=t.id, dia=data.dia, horas=Decimal(str(data.horas)), motivo=data.motivo,
                         estado="vigente", creado_por=u.id)
        db.add(h)
    db.flush()
    audit(db, u.id, "actualizar" if antes else "crear", "he_programada", h.id, antes, to_dict(h))
    db.commit()
    db.refresh(h)
    return _out(h, t)


@r.delete("/{he_id}")
def anular(he_id: int, db: Session = Depends(get_db), u: Usuario = Depends(require("jefe", "rrhh", "admin"))):
    h = db.get(HEProgramada, he_id)
    if not h:
        raise HTTPException(404, "Programación no encontrada")
    t = db.get(Trabajador, h.trabajador_id)
    _alcance(u, t)
    exigir_abierto_trabajador(db, t.id, h.dia.strftime("%Y-%m"))
    antes = to_dict(h)
    h.estado, h.actualizado_en = "anulada", datetime.now(timezone.utc)
    audit(db, u.id, "anular", "he_programada", h.id, antes, to_dict(h))
    db.commit()
    return _out(h, t)
