"""Sprint 3: Reportes consolidados y export a Excel/CSV."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Usuario

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/consolidado-mensual")
def consolidado_mensual(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    empresa_id: Optional[int] = None,
    unidad_id: Optional[int] = None,
    trabajador_id: Optional[int] = None,
    formato: str = Query("json", pattern=r"^(json|excel|csv)$"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Consolidado mensual por trabajador (implementación pendiente)."""
    if user.rol not in ("rrhh", "admin", "jefe"):
        raise HTTPException(403, "No autorizado")
    
    return {"periodo": periodo, "registros": [], "totales": {}}


@router.get("/conceptos-remunerativos")
def conceptos_remunerativos(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    empresa_id: int = Query(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Export de conceptos remunerativos (implementación pendiente)."""
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    return {"periodo": periodo, "empresa_id": empresa_id, "trabajadores": []}
