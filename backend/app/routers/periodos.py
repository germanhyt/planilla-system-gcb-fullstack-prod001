"""Sprint 3: Cierre y reapertura de periodos contables."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Usuario
from ..schemas import CierrePeriodoIn, ReaperturaPeriodoIn

router = APIRouter(prefix="/periodos", tags=["periodos"])


@router.post("/cerrar")
def cerrar_periodo(
    data: CierrePeriodoIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Cerrar periodo mensual (implementación pendiente)."""
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    return {"periodo": data.periodo, "estado": "cerrado"}


@router.post("/reabrir/{cierre_id}")
def reabrir_periodo(
    cierre_id: int,
    data: ReaperturaPeriodoIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Reabrir periodo (implementación pendiente)."""
    if user.rol != "admin":
        raise HTTPException(403, "Solo admin")
    
    return {"id": cierre_id, "estado": "reabierto"}


@router.get("/historial")
def historial_cierres(
    empresa_id: int = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Historial de cierres (implementación pendiente)."""
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    return []
