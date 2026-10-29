"""API de regularización de horas extra no programadas (bandeja del jefe). Sprint 2."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit import audit
from ..db import get_db
from ..deps import current_user
from ..models import Asistencia, RegularizacionHE, Trabajador, Usuario
from ..schemas import RegularizacionDecision

r = APIRouter(prefix="/regularizaciones", tags=["regularizaciones"])


@r.get("/")
def listar_pendientes(db: Session = Depends(get_db), u: Usuario = Depends(current_user)):
    """Lista las regularizaciones pendientes para la unidad del jefe."""
    if u.rol not in ("jefe", "rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    query = db.query(RegularizacionHE).join(Trabajador).filter(
        RegularizacionHE.estado == "pendiente"
    )
    
    if u.rol == "jefe":
        if not u.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        query = query.filter(Trabajador.unidad_id == u.unidad_id)
    
    regs = query.order_by(RegularizacionHE.creado_en.desc()).limit(100).all()
    
    resultado = []
    for reg in regs:
        trabajador = db.query(Trabajador).get(reg.trabajador_id)
        asistencia = db.query(Asistencia).get(reg.asistencia_id)
        
        resultado.append({
            "id": reg.id,
            "trabajador": {
                "id": trabajador.id,
                "codigo": trabajador.codigo,
                "nombres": trabajador.nombres,
                "apellidos": trabajador.apellidos
            },
            "dia_operativo": str(asistencia.dia_operativo) if asistencia else None,
            "horas_exceso": float(reg.horas_exceso),
            "estado": reg.estado,
            "creado_en": reg.creado_en.isoformat()
        })
    
    return resultado


@r.post("/{reg_id}/decidir")
def decidir_regularizacion(
    reg_id: int,
    decision: RegularizacionDecision,
    db: Session = Depends(get_db),
    u: Usuario = Depends(current_user)
):
    """Aprueba o rechaza una regularización de horas extra."""
    if u.rol not in ("jefe", "rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    reg = db.query(RegularizacionHE).get(reg_id)
    if not reg:
        raise HTTPException(404, "Regularización no encontrada")
    
    if reg.estado != "pendiente":
        raise HTTPException(400, "La regularización ya fue procesada")
    
    trabajador = db.query(Trabajador).get(reg.trabajador_id)
    if u.rol == "jefe" and trabajador.unidad_id != u.unidad_id:
        raise HTTPException(403, "Solo puede regularizar trabajadores de su unidad")
    
    if decision.aprobar and not decision.destino:
        raise HTTPException(400, "Debe especificar destino (pago/compensacion/mixto) al aprobar")
    
    antes = {
        "estado": reg.estado,
        "destino": reg.destino,
        "observacion": reg.observacion
    }
    
    reg.estado = "aprobado" if decision.aprobar else "rechazado"
    reg.destino = decision.destino if decision.aprobar else None
    reg.observacion = decision.observacion
    reg.decision_por = u.id
    reg.decision_en = datetime.utcnow()
    
    if decision.aprobar:
        asistencia = db.query(Asistencia).get(reg.asistencia_id)
        if asistencia:
            if decision.destino == "pago":
                if reg.horas_exceso <= 2:
                    asistencia.horas_extra_25 += reg.horas_exceso
                else:
                    asistencia.horas_extra_25 += 2
                    asistencia.horas_extra_35 += (reg.horas_exceso - 2)
            
            asistencia.exceso_no_programado = 0
    
    db.commit()
    
    despues = {
        "estado": reg.estado,
        "destino": reg.destino,
        "observacion": reg.observacion,
        "decision_por": u.id,
        "decision_en": reg.decision_en.isoformat()
    }
    
    audit(db, u.id, "regularizar_he", "regularizacion", str(reg.id), antes, despues)
    
    return {"id": reg.id, "estado": reg.estado, "destino": reg.destino}


@r.get("/trabajador/{trabajador_id}")
def listar_por_trabajador(
    trabajador_id: int,
    db: Session = Depends(get_db),
    u: Usuario = Depends(current_user)
):
    """Lista el historial de regularizaciones de un trabajador."""
    trabajador = db.query(Trabajador).get(trabajador_id)
    if not trabajador:
        raise HTTPException(404, "Trabajador no encontrado")
    
    if u.rol == "trabajador":
        mi_trabajador = db.query(Trabajador).filter(Trabajador.usuario_id == u.id).first()
        if not mi_trabajador or mi_trabajador.id != trabajador_id:
            raise HTTPException(403, "Solo puede ver sus propias regularizaciones")
    
    if u.rol == "jefe" and trabajador.unidad_id != u.unidad_id:
        raise HTTPException(403, "Solo puede ver trabajadores de su unidad")
    
    regs = db.query(RegularizacionHE).filter(
        RegularizacionHE.trabajador_id == trabajador_id
    ).order_by(RegularizacionHE.creado_en.desc()).limit(50).all()
    
    return [{
        "id": r.id,
        "horas_exceso": float(r.horas_exceso),
        "estado": r.estado,
        "destino": r.destino,
        "observacion": r.observacion,
        "creado_en": r.creado_en.isoformat(),
        "decision_en": r.decision_en.isoformat() if r.decision_en else None
    } for r in regs]
