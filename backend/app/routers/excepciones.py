"""Sprint 3: Dashboard de excepciones y alertas."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Usuario
from ..schemas import FaltaJustificadaIn

router = APIRouter(prefix="/excepciones", tags=["excepciones"])


@router.get("/faltas-sin-justificar")
def listar_faltas_sin_justificar(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    unidad_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Faltas sin justificar (implementación pendiente)."""
    if user.rol == "trabajador":
        raise HTTPException(403, "No autorizado")
    
    return []


@router.get("/tardanzas-recurrentes")
def listar_tardanzas_recurrentes(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    min_tardanzas: int = Query(3, ge=1),
    unidad_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Tardanzas recurrentes (implementación pendiente)."""
    if user.rol == "trabajador":
        raise HTTPException(403, "No autorizado")
    
    return []


@router.get("/marcas-fuera-geocerca")
def listar_marcas_fuera_geocerca(
    desde: date = Query(...),
    hasta: date = Query(...),
    unidad_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Marcas fuera de geocerca (implementación pendiente)."""
    if user.rol == "trabajador":
        raise HTTPException(403, "No autorizado")
    
    return []


@router.get("/part-time-riesgo")
def reporte_part_time_riesgo(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Part-time con riesgo normativo (implementación pendiente)."""
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    return []


@router.post("/justificar-falta")
def justificar_falta(
    data: FaltaJustificadaIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Justificar falta (implementación pendiente)."""
    if user.rol not in ("jefe", "rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    return {"trabajador_id": data.trabajador_id, "dia": data.dia.isoformat()}
