"""Sprint 4: horario asignado por trabajador con vigencia (jefe de su unidad; RRHH/admin todos).

- `patron`: lista de semanas (1..8), cada una con 7 ids de plantilla (lunes..domingo; null = descanso).
- Al crear, la asignación abierta anterior que se solape se cierra el día previo (no se borra: historial).
- Bloqueo 409 si `vigente_desde` cae en un periodo cerrado.
- GET /asignaciones-horario/calendario resuelve día a día (plan semanal > asignación > sin horario).
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit import audit
from ..cierre import exigir_abierto_trabajador
from ..db import get_db
from ..deps import current_user, require
from ..engine import refrigerio_efectivo, resolver_turno_dia
from ..models import HorarioAsignacion, TipoContrato, Trabajador, TurnoPlantilla, Usuario

r = APIRouter(prefix="/asignaciones-horario", tags=["asignaciones_horario"])


class AsignacionIn(BaseModel):
    trabajador_id: int
    vigente_desde: date
    vigente_hasta: Optional[date] = None
    patron: list[list[Optional[int]]] = Field(min_length=1, max_length=8)
    nota: Optional[str] = Field(None, max_length=500)


def _trab(db: Session, u: Usuario, trabajador_id: int, escritura: bool) -> Trabajador:
    t = db.get(Trabajador, trabajador_id)
    if not t:
        raise HTTPException(404, "Trabajador no encontrado")
    if u.rol == "jefe" and t.unidad_id != u.unidad_id:
        raise HTTPException(403, "Solo puede asignar horarios a trabajadores de su unidad")
    if u.rol == "trabajador" and (escritura or t.usuario_id != u.id):
        raise HTTPException(403, "Sin permiso")
    return t


def _out(a: HorarioAsignacion) -> dict:
    return {"id": a.id, "trabajador_id": a.trabajador_id, "vigente_desde": a.vigente_desde.isoformat(),
            "vigente_hasta": a.vigente_hasta.isoformat() if a.vigente_hasta else None,
            "patron": a.patron, "nota": a.nota, "creado_por": a.creado_por}


@r.get("")
def listar(trabajador_id: int, db: Session = Depends(get_db), u: Usuario = Depends(current_user)):
    _trab(db, u, trabajador_id, escritura=False)
    q = db.query(HorarioAsignacion).filter(HorarioAsignacion.trabajador_id == trabajador_id)
    return [_out(a) for a in q.order_by(HorarioAsignacion.vigente_desde.desc(), HorarioAsignacion.id.desc())]


@r.post("", status_code=201)
def crear(body: AsignacionIn, db: Session = Depends(get_db), u: Usuario = Depends(require("jefe", "rrhh", "admin"))):
    t = _trab(db, u, body.trabajador_id, escritura=True)
    if body.vigente_hasta and body.vigente_hasta < body.vigente_desde:
        raise HTTPException(422, "vigente_hasta debe ser posterior a vigente_desde")
    for semana in body.patron:
        if len(semana) != 7:
            raise HTTPException(422, "Cada semana del patrón debe tener 7 días (lunes..domingo)")
        for pid in semana:
            if pid is None:
                continue
            p = db.get(TurnoPlantilla, pid)
            if not p or not p.activo:
                raise HTTPException(422, f"Plantilla {pid} no existe o está inactiva")
            if p.unidad_id != t.unidad_id:
                raise HTTPException(422, f"La plantilla {p.nombre} no pertenece a la unidad del trabajador")
    exigir_abierto_trabajador(db, t.id, body.vigente_desde.strftime("%Y-%m"))
    # Cierra la(s) asignación(es) previa(s) que sigan vigentes desde la nueva fecha.
    previas = db.query(HorarioAsignacion).filter(
        HorarioAsignacion.trabajador_id == t.id, HorarioAsignacion.vigente_desde < body.vigente_desde,
        (HorarioAsignacion.vigente_hasta.is_(None)) | (HorarioAsignacion.vigente_hasta >= body.vigente_desde)).all()
    for p in previas:
        p.vigente_hasta = body.vigente_desde - timedelta(days=1)
    a = HorarioAsignacion(trabajador_id=t.id, vigente_desde=body.vigente_desde, vigente_hasta=body.vigente_hasta,
                          patron=body.patron, nota=body.nota, creado_por=u.id)
    db.add(a)
    db.flush()
    audit(db, u.id, "crear", "horario_asignacion", a.id, None, _out(a))
    db.commit()
    return _out(a)


@r.delete("/{asig_id}")
def eliminar(asig_id: int, db: Session = Depends(get_db), u: Usuario = Depends(require("jefe", "rrhh", "admin"))):
    a = db.get(HorarioAsignacion, asig_id)
    if not a:
        raise HTTPException(404, "Asignación no encontrada")
    _trab(db, u, a.trabajador_id, escritura=True)
    exigir_abierto_trabajador(db, a.trabajador_id, a.vigente_desde.strftime("%Y-%m"))
    antes = _out(a)
    db.delete(a)
    audit(db, u.id, "eliminar", "horario_asignacion", asig_id, antes, None)
    db.commit()
    return {"ok": True}


@r.get("/calendario")
def calendario(trabajador_id: int, desde: date = Query(...), hasta: date = Query(...),
               db: Session = Depends(get_db), u: Usuario = Depends(current_user)):
    t = _trab(db, u, trabajador_id, escritura=False)
    if (hasta - desde).days > 62:
        raise HTTPException(422, "Rango máximo 62 días")
    tc = db.get(TipoContrato, t.tipo_contrato_id)
    dias, d = [], desde
    while d <= hasta:
        pid, origen = resolver_turno_dia(db, t.id, d)
        p = db.get(TurnoPlantilla, pid) if pid else None
        item = {"dia": d.isoformat(), "origen": origen, "plantilla_id": pid}
        if p:
            ref = refrigerio_efectivo(db, t, p)
            ini, fin = p.inicio.hour * 60 + p.inicio.minute, p.fin.hour * 60 + p.fin.minute
            fin += 1440 if fin < ini else 0
            item.update(plantilla=p.nombre, inicio=p.inicio.strftime("%H:%M"), fin=p.fin.strftime("%H:%M"),
                        refrigerio_min=ref, horas_programadas=round((fin - ini - ref) / 60, 2))
        dias.append(item)
        d += timedelta(days=1)
    jornada = t.jornada_diaria_min or (tc.jornada_diaria_min if tc else None)
    return {"trabajador_id": t.id, "contrato": tc.codigo if tc else None, "jornada_diaria_min": jornada,
            "horas_mes": tc.horas_mes if tc else None, "dias": dias}
