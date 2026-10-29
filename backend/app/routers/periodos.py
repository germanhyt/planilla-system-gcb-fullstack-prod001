"""Sprint 3: Cierre y reapertura de periodos contables."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit import audit
from ..db import get_db
from ..deps import current_user
from ..models import Asistencia, CierrePeriodo, RegularizacionHE, Trabajador, Usuario
from ..schemas import CierrePeriodoIn, ReaperturaPeriodoIn

router = APIRouter(prefix="/periodos", tags=["periodos"])


@router.post("/cerrar")
def cerrar_periodo(
    data: CierrePeriodoIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """
    Cerrar periodo mensual: bloquea recálculo de asistencia y nuevas marcas para ese mes operativo.
    Solo RRHH y admin pueden cerrar.
    """
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    # Verificar que no esté ya cerrado
    existe = db.query(CierrePeriodo).filter(
        CierrePeriodo.empresa_id == data.empresa_id,
        CierrePeriodo.periodo == data.periodo,
        CierrePeriodo.estado == "cerrado"
    ).first()
    
    if existe:
        raise HTTPException(400, f"Periodo {data.periodo} ya está cerrado para empresa {data.empresa_id}")
    
    # Verificar que no haya regularizaciones pendientes
    pendientes = db.query(RegularizacionHE).join(Asistencia).filter(
        Asistencia.periodo == data.periodo,
        RegularizacionHE.estado == "pendiente"
    ).count()
    
    if pendientes > 0:
        raise HTTPException(
            400, 
            f"Hay {pendientes} regularizaciones pendientes. Debe resolverlas antes de cerrar el periodo."
        )
    
    # Crear cierre
    cierre = CierrePeriodo(
        empresa_id=data.empresa_id,
        periodo=data.periodo,
        cerrado_por=user.id,
        estado="cerrado"
    )
    db.add(cierre)
    
    # Marcar todas las asistencias de ese periodo como cerradas
    db.query(Asistencia).join(
        Trabajador, Asistencia.trabajador_id == Trabajador.id
    ).filter(
        Asistencia.periodo == data.periodo,
        Trabajador.empresa_id == data.empresa_id
    ).update({Asistencia.periodo_cerrado: True}, synchronize_session=False)
    
    db.commit()
    db.refresh(cierre)
    
    audit(db, user.id, "cerrar_periodo", "cierre_periodo", str(cierre.id), 
          None, {"periodo": data.periodo, "empresa_id": data.empresa_id})
    
    return {
        "id": cierre.id,
        "periodo": cierre.periodo,
        "empresa_id": cierre.empresa_id,
        "estado": cierre.estado,
        "cerrado_en": cierre.cerrado_en.isoformat()
    }


@router.post("/reabrir/{cierre_id}")
def reabrir_periodo(
    cierre_id: int,
    data: ReaperturaPeriodoIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """
    Reabrir periodo cerrado con razón auditada. Solo admin puede reabrir.
    Crea nueva versión del cierre para mantener historial.
    """
    if user.rol != "admin":
        raise HTTPException(403, "Solo admin puede reabrir periodos")
    
    cierre = db.query(CierrePeriodo).filter(CierrePeriodo.id == cierre_id).first()
    if not cierre:
        raise HTTPException(404, "Cierre no encontrado")
    
    if cierre.estado != "cerrado":
        raise HTTPException(400, "El periodo ya está reabierto")
    
    # Actualizar el cierre existente
    cierre.estado = "reabierto"
    cierre.reabierto_por = user.id
    cierre.reabierto_en = db.execute("SELECT NOW()").scalar()
    cierre.razon_reapertura = data.razon_reapertura
    
    # Desmarcar asistencias como cerradas para permitir recálculo
    db.query(Asistencia).join(
        Trabajador, Asistencia.trabajador_id == Trabajador.id
    ).filter(
        Asistencia.periodo == cierre.periodo,
        Trabajador.empresa_id == cierre.empresa_id
    ).update({Asistencia.periodo_cerrado: False}, synchronize_session=False)
    
    db.commit()
    db.refresh(cierre)
    
    audit(db, user.id, "reabrir_periodo", "cierre_periodo", str(cierre.id),
          {"estado": "cerrado"}, {"estado": "reabierto", "razon": data.razon_reapertura})
    
    return {
        "id": cierre.id,
        "periodo": cierre.periodo,
        "empresa_id": cierre.empresa_id,
        "estado": cierre.estado,
        "reabierto_en": cierre.reabierto_en.isoformat() if cierre.reabierto_en else None,
        "razon_reapertura": cierre.razon_reapertura
    }


@router.get("/historial")
def historial_cierres(
    empresa_id: int = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Historial de cierres y reaperturas (con auditoría)."""
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    q = db.query(CierrePeriodo)
    if empresa_id:
        q = q.filter(CierrePeriodo.empresa_id == empresa_id)
    
    cierres = q.order_by(CierrePeriodo.cerrado_en.desc()).all()
    
    return [
        {
            "id": c.id,
            "empresa_id": c.empresa_id,
            "periodo": c.periodo,
            "estado": c.estado,
            "cerrado_por": c.cerrado_por,
            "cerrado_en": c.cerrado_en.isoformat(),
            "reabierto_por": c.reabierto_por,
            "reabierto_en": c.reabierto_en.isoformat() if c.reabierto_en else None,
            "razon_reapertura": c.razon_reapertura
        }
        for c in cierres
    ]
