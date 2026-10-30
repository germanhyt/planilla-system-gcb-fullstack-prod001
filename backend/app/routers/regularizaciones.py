"""API de regularización de horas extra no programadas (bandeja del jefe). Sprint 2."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit import audit
from ..db import get_db
from ..deps import current_user
from ..models import Asistencia, BancoHorasCompensatorias, RegularizacionHE, Trabajador, Usuario
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
        from .bandeja import destino_default
        asi_def = db.get(Asistencia, reg.asistencia_id)
        decision.destino = destino_default(db, trabajador.empresa_id, asi_def.dia_operativo if asi_def else reg.creado_en.date())
    if decision.aprobar and decision.destino == "mixto" and decision.horas_pago is not None and not (
            0 < decision.horas_pago < float(reg.horas_exceso)):
        raise HTTPException(400, "horas_pago debe estar entre 0 y las horas de exceso (exclusivo)")
    
    antes = {
        "estado": reg.estado,
        "destino": reg.destino,
        "observacion": reg.observacion
    }
    
    reg.estado = "aprobado" if decision.aprobar else "rechazado"
    reg.destino = decision.destino if decision.aprobar else None
    reg.observacion = decision.observacion
    reg.decision_por = u.id
    reg.decision_en = datetime.now(timezone.utc)
    
    if decision.aprobar:
        asistencia = db.query(Asistencia).get(reg.asistencia_id)
        if asistencia:
            if decision.destino == "pago":
                horas_exceso_float = float(reg.horas_exceso)
                if horas_exceso_float <= 2:
                    asistencia.horas_extra_25 = float(asistencia.horas_extra_25) + horas_exceso_float
                else:
                    asistencia.horas_extra_25 = float(asistencia.horas_extra_25) + 2
                    asistencia.horas_extra_35 = float(asistencia.horas_extra_35) + (horas_exceso_float - 2)
            
            elif decision.destino == "compensacion":
                # Crear crédito en banco de horas compensatorias
                ultimo = db.query(BancoHorasCompensatorias).filter(
                    BancoHorasCompensatorias.trabajador_id == trabajador.id
                ).order_by(BancoHorasCompensatorias.creado_en.desc(), BancoHorasCompensatorias.id.desc()).first()
                
                saldo_anterior = float(ultimo.saldo_nuevo) if ultimo else 0.0
                saldo_nuevo = saldo_anterior + float(reg.horas_exceso)
                
                # Configurar expiración: 90 días por defecto
                dias_expiracion = 90
                fecha_expira = asistencia.dia_operativo + timedelta(days=dias_expiracion)
                
                banco_mov = BancoHorasCompensatorias(
                    trabajador_id=trabajador.id,
                    fecha_movimiento=asistencia.dia_operativo,
                    tipo="credito",
                    horas=float(reg.horas_exceso),
                    saldo_anterior=saldo_anterior,
                    saldo_nuevo=saldo_nuevo,
                    origen=f"HE compensatoria aprobada (reg #{reg.id})",
                    regularizacion_id=reg.id,
                    asistencia_id=reg.asistencia_id,
                    dias_expiracion=dias_expiracion,
                    fecha_expira=fecha_expira
                )
                db.add(banco_mov)
            
            elif decision.destino == "mixto":
                # 50% a pago, 50% a compensación
                horas_pago = decision.horas_pago if decision.horas_pago is not None else float(reg.horas_exceso) / 2
                horas_comp = float(reg.horas_exceso) - horas_pago
                
                # Pago
                if horas_pago <= 2:
                    asistencia.horas_extra_25 = float(asistencia.horas_extra_25) + horas_pago
                else:
                    asistencia.horas_extra_25 = float(asistencia.horas_extra_25) + 2
                    asistencia.horas_extra_35 = float(asistencia.horas_extra_35) + (horas_pago - 2)
                
                # Compensación
                ultimo = db.query(BancoHorasCompensatorias).filter(
                    BancoHorasCompensatorias.trabajador_id == trabajador.id
                ).order_by(BancoHorasCompensatorias.creado_en.desc(), BancoHorasCompensatorias.id.desc()).first()
                
                saldo_anterior = float(ultimo.saldo_nuevo) if ultimo else 0.0
                saldo_nuevo = saldo_anterior + horas_comp
                
                dias_expiracion = 90
                fecha_expira = asistencia.dia_operativo + timedelta(days=dias_expiracion)
                
                banco_mov = BancoHorasCompensatorias(
                    trabajador_id=trabajador.id,
                    fecha_movimiento=asistencia.dia_operativo,
                    tipo="credito",
                    horas=horas_comp,
                    saldo_anterior=saldo_anterior,
                    saldo_nuevo=saldo_nuevo,
                    origen=f"HE mixta aprobada (reg #{reg.id}) - parte compensatoria",
                    regularizacion_id=reg.id,
                    asistencia_id=reg.asistencia_id,
                    dias_expiracion=dias_expiracion,
                    fecha_expira=fecha_expira
                )
                db.add(banco_mov)
            
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
