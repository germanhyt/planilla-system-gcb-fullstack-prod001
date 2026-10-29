"""API de regularización de horas extra no programadas (bandeja del jefe). Sprint 2."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import auditar
from ..banco_horas import registrar_credito
from ..db import get_db
from ..deps import get_current_user
from ..models import Asistencia, RegularizacionHE, Trabajador, Usuario
from ..schemas import RegularizacionDecision

r = APIRouter(prefix="/regularizaciones", tags=["regularizaciones"])


@r.get("/")
async def listar_pendientes(db: AsyncSession = Depends(get_db), u: Usuario = Depends(get_current_user)):
    """Lista las regularizaciones pendientes para la unidad del jefe."""
    if u.rol not in ("jefe", "rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    query = (
        select(RegularizacionHE, Trabajador, Asistencia)
        .join(Trabajador, RegularizacionHE.trabajador_id == Trabajador.id)
        .join(Asistencia, RegularizacionHE.asistencia_id == Asistencia.id)
        .where(RegularizacionHE.estado == "pendiente")
    )
    
    if u.rol == "jefe":
        if not u.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        query = query.where(Trabajador.unidad_id == u.unidad_id)
    
    query = query.order_by(RegularizacionHE.creado_en.desc()).limit(100)
    result = await db.execute(query)
    regs = result.all()
    
    return [
        {
            "id": reg.id,
            "trabajador": {
                "id": trab.id,
                "codigo": trab.codigo,
                "nombres": trab.nombres,
                "apellidos": trab.apellidos
            },
            "dia_operativo": asist.dia_operativo.isoformat() if asist else None,
            "horas_exceso": float(reg.horas_exceso),
            "estado": reg.estado,
            "creado_en": reg.creado_en.isoformat()
        }
        for reg, trab, asist in regs
    ]


@r.post("/{reg_id}/decidir")
async def decidir_regularizacion(
    reg_id: int,
    decision: RegularizacionDecision,
    db: AsyncSession = Depends(get_db),
    u: Usuario = Depends(get_current_user)
):
    """Aprueba o rechaza una regularización de horas extra. Sprint 3: integra banco de horas compensatorias."""
    if u.rol not in ("jefe", "rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    q = select(RegularizacionHE).where(RegularizacionHE.id == reg_id)
    result = await db.execute(q)
    reg = result.scalar_one_or_none()
    if not reg:
        raise HTTPException(404, "Regularización no encontrada")
    
    if reg.estado != "pendiente":
        raise HTTPException(400, "La regularización ya fue procesada")
    
    q = select(Trabajador).where(Trabajador.id == reg.trabajador_id)
    result = await db.execute(q)
    trabajador = result.scalar_one_or_none()
    if u.rol == "jefe":
        if not u.unidad_id or trabajador.unidad_id != u.unidad_id:
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
    reg.decision_en = datetime.now()
    
    if decision.aprobar:
        q = select(Asistencia).where(Asistencia.id == reg.asistencia_id)
        result = await db.execute(q)
        asistencia = result.scalar_one_or_none()
        
        if asistencia:
            if decision.destino in ("pago", "mixto"):
                horas_pago = reg.horas_exceso if decision.destino == "pago" else reg.horas_exceso / 2
                if horas_pago <= 2:
                    asistencia.horas_extra_25 += horas_pago
                else:
                    asistencia.horas_extra_25 += 2
                    asistencia.horas_extra_35 += (horas_pago - 2)
            
            if decision.destino in ("compensacion", "mixto"):
                horas_comp = reg.horas_exceso if decision.destino == "compensacion" else reg.horas_exceso / 2
                await registrar_credito(
                    db,
                    trabajador_id=reg.trabajador_id,
                    horas=horas_comp,
                    origen=f"HE compensatoria aprobada - día {asistencia.dia_operativo}",
                    regularizacion_id=reg.id,
                    dias_expiracion=90,
                    fecha_movimiento=asistencia.dia_operativo,
                )
            
            asistencia.exceso_no_programado = 0
    
    await db.commit()
    
    despues = {
        "estado": reg.estado,
        "destino": reg.destino,
        "observacion": reg.observacion,
        "decision_por": u.id,
        "decision_en": reg.decision_en.isoformat()
    }
    
    await auditar(db, u.id, "regularizar_he", "regularizacion", str(reg.id), antes, despues)
    
    return {"id": reg.id, "estado": reg.estado, "destino": reg.destino}



@r.get("/trabajador/{trabajador_id}")
async def listar_por_trabajador(
    trabajador_id: int,
    db: AsyncSession = Depends(get_db),
    u: Usuario = Depends(get_current_user)
):
    """Lista el historial de regularizaciones de un trabajador."""
    q = select(Trabajador).where(Trabajador.id == trabajador_id)
    result = await db.execute(q)
    trabajador = result.scalar_one_or_none()
    if not trabajador:
        raise HTTPException(404, "Trabajador no encontrado")
    
    if u.rol == "trabajador":
        q = select(Trabajador).where(Trabajador.usuario_id == u.id)
        result = await db.execute(q)
        mi_trabajador = result.scalar_one_or_none()
        if not mi_trabajador or mi_trabajador.id != trabajador_id:
            raise HTTPException(403, "Solo puede ver sus propias regularizaciones")
    
    if u.rol == "jefe" and trabajador.unidad_id != u.unidad_id:
        raise HTTPException(403, "Solo puede ver trabajadores de su unidad")
    
    q = (
        select(RegularizacionHE)
        .where(RegularizacionHE.trabajador_id == trabajador_id)
        .order_by(RegularizacionHE.creado_en.desc())
        .limit(50)
    )
    result = await db.execute(q)
    regs = result.scalars().all()
    
    return [{
        "id": r.id,
        "horas_exceso": float(r.horas_exceso),
        "estado": r.estado,
        "destino": r.destino,
        "observacion": r.observacion,
        "creado_en": r.creado_en.isoformat(),
        "decision_en": r.decision_en.isoformat() if r.decision_en else None
    } for r in regs]
