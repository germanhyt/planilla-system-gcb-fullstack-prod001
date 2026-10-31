"""Bono nocturno 3 AM: concepto interno (no es el recargo nocturno legal).

Administración registra cantidad y monto (S/) por trabajador y periodo; RRHH/admin distinto aprueba o rechaza
(segregación de funciones). Todo queda en historial y auditoría. Periodo cerrado -> 409.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..alcance import empresa_alcance
from ..audit import audit, to_dict
from ..cierre import esta_cerrado, exigir_abierto
from ..db import get_db
from ..deps import require
from ..paginacion import paginar_sql, params_pagina
from ..models import BonoNocturno, BonoNocturnoHistorial, Trabajador, Usuario
from ..schemas import BonoDecision, BonoIn

r = APIRouter(prefix="/bonos-nocturnos", tags=["bono nocturno 3 AM"])


def _ip(req):
    return req.client.host if req.client else None


def _out(db: Session, b: BonoNocturno, t: Optional[Trabajador] = None, nombres: Optional[dict] = None) -> dict:
    t = t or db.get(Trabajador, b.trabajador_id)
    d = to_dict(b)
    d |= {"trabajador_codigo": t.codigo if t else None, "trabajador": f"{t.nombres} {t.apellidos}" if t else None,
          "empresa_id": t.empresa_id if t else None,
          "periodo_cerrado": bool(t and esta_cerrado(db, t.empresa_id, b.periodo))}
    if nombres is not None:
        d["registrado_por_email"] = nombres.get(b.registrado_por)
        d["aprobado_por_email"] = nombres.get(b.aprobado_por)
    return d


@r.get("")
def listar(periodo: Optional[str] = None, empresa_id: Optional[int] = None, estado: Optional[str] = None,
           db: Session = Depends(get_db), u: Usuario = Depends(require("rrhh", "admin")),
           pag: Optional[dict] = Depends(params_pagina)):
    empresa_id = empresa_alcance(u, empresa_id)
    q = select(BonoNocturno, Trabajador).join(Trabajador, Trabajador.id == BonoNocturno.trabajador_id) \
        .order_by(Trabajador.codigo, BonoNocturno.id)
    if periodo:
        q = q.where(BonoNocturno.periodo == periodo)
    if empresa_id:
        q = q.where(Trabajador.empresa_id == empresa_id)
    if estado:
        q = q.where(BonoNocturno.estado == estado)
    nombres = dict(db.execute(select(Usuario.id, Usuario.email)).all())
    if pag is None:
        return [_out(db, b, t, nombres) for b, t in db.execute(q)]
    # S8 paso 7: paginado en la BD (q por código/nombre/periodo; orden estable por id)
    return paginar_sql(db, q.order_by(None), pag, lambda r: _out(db, r[0], r[1], nombres),
                       buscar=(Trabajador.codigo, Trabajador.nombres, Trabajador.apellidos, BonoNocturno.periodo),
                       orden={"trabajador_codigo": Trabajador.codigo, "trabajador": Trabajador.apellidos,
                              "periodo": BonoNocturno.periodo, "estado": BonoNocturno.estado,
                              "cantidad": BonoNocturno.cantidad, "monto": BonoNocturno.monto},
                       orden_def=(Trabajador.codigo,), desempate=(BonoNocturno.id,))


@r.post("", status_code=201)
def registrar(body: BonoIn, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(require("admin"))):
    """Registra o corrige (vuelve a 'registrado') cantidad y monto del bono de un trabajador en un periodo."""
    t = db.get(Trabajador, body.trabajador_id)
    if not t:
        raise HTTPException(404, "Trabajador no existe")
    exigir_abierto(db, t.empresa_id, body.periodo)
    b = db.scalar(select(BonoNocturno).where(BonoNocturno.trabajador_id == body.trabajador_id,
                                             BonoNocturno.periodo == body.periodo))
    antes = to_dict(b) if b else None
    if b:
        b.cantidad, b.monto, b.observacion = body.cantidad, body.monto, body.observacion
        b.estado, b.registrado_por, b.aprobado_por, b.aprobado_en = "registrado", u.id, None, None
        accion = "corregir"
    else:
        b = BonoNocturno(**body.model_dump(), registrado_por=u.id, estado="registrado")
        db.add(b)
        accion = "registrar"
    db.flush()
    db.add(BonoNocturnoHistorial(bono_id=b.id, usuario_id=u.id, accion=accion, cantidad=b.cantidad, monto=b.monto,
                                 estado=b.estado, comentario=body.observacion))
    audit(db, u.id, "crear" if not antes else "actualizar", "bono_nocturno", b.id, antes, to_dict(b), _ip(request))
    db.commit()
    return _out(db, b, t)


@r.post("/{bid}/decision")
def decidir(bid: int, body: BonoDecision, request: Request, db: Session = Depends(get_db),
            u: Usuario = Depends(require("rrhh", "admin"))):
    b = db.get(BonoNocturno, bid)
    if not b:
        raise HTTPException(404, "Bono no existe")
    t = db.get(Trabajador, b.trabajador_id)
    exigir_abierto(db, t.empresa_id, b.periodo)
    if b.estado != "registrado":
        raise HTTPException(409, f"El bono ya está {b.estado}")
    if b.registrado_por == u.id:
        raise HTTPException(403, "Quien registra no puede aprobar (segregación de funciones)")
    if body.aprobar and b.monto is None:
        raise HTTPException(422, "Defina el monto del bono antes de aprobarlo")
    antes = to_dict(b)
    b.estado = "aprobado" if body.aprobar else "rechazado"
    b.aprobado_por = u.id
    b.aprobado_en = datetime.now(timezone.utc)
    db.add(BonoNocturnoHistorial(bono_id=b.id, usuario_id=u.id, accion=b.estado, cantidad=b.cantidad, monto=b.monto,
                                 estado=b.estado, comentario=body.comentario))
    audit(db, u.id, "aprobar" if body.aprobar else "rechazar", "bono_nocturno", b.id, antes, to_dict(b), _ip(request))
    db.commit()
    return _out(db, b, t)


@r.get("/{bid}/historial")
def historial(bid: int, db: Session = Depends(get_db), _: Usuario = Depends(require("rrhh", "admin"))):
    return [to_dict(h) for h in db.scalars(select(BonoNocturnoHistorial).where(BonoNocturnoHistorial.bono_id == bid)
                                           .order_by(BonoNocturnoHistorial.id))]