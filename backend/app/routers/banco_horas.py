"""Sprint 3: Consultas de banco de horas compensatorias."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..banco_horas import (
    get_saldo_actual,
    historial_trabajador,
    listar_proximas_expiraciones,
)
from ..db import get_db
from ..deps import current_user
from ..models import Trabajador, Usuario

router = APIRouter(prefix="/banco-horas", tags=["banco_horas"])


@router.get("/saldo/{trabajador_id}")
def consultar_saldo(
    trabajador_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """
    Consulta saldo actual de horas compensatorias.
    Trabajador: solo su propio saldo. Jefe/RRHH/Admin: cualquier trabajador (con filtro de unidad para jefe).
    """
    if user.rol == "trabajador":
        mi_trab = db.query(Trabajador).filter(Trabajador.usuario_id == user.id).first()
        if not mi_trab or mi_trab.id != trabajador_id:
            raise HTTPException(403, "Solo puede ver su propio saldo")
    
    if user.rol == "jefe":
        trab = db.query(Trabajador).filter(Trabajador.id == trabajador_id).first()
        if not trab or trab.unidad_id != user.unidad_id:
            raise HTTPException(403, "Solo puede ver trabajadores de su unidad")
    
    return {"trabajador_id": trabajador_id, "saldo_horas": 0.0}


@router.get("/historial/{trabajador_id}")
def consultar_historial(
    trabajador_id: int,
    limite: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """
    Historial de movimientos de horas compensatorias.
    """
    if user.rol == "trabajador":
        mi_trab = db.query(Trabajador).filter(Trabajador.usuario_id == user.id).first()
        if not mi_trab or mi_trab.id != trabajador_id:
            raise HTTPException(403, "Solo puede ver su propio historial")
    
    if user.rol == "jefe":
        trab = db.query(Trabajador).filter(Trabajador.id == trabajador_id).first()
        if not trab or trab.unidad_id != user.unidad_id:
            raise HTTPException(403, "Solo puede ver trabajadores de su unidad")
    
    return {"trabajador_id": trabajador_id, "movimientos": []}


@router.get("/expiraciones")
def proximas_expiraciones(
    dias_alerta: int = Query(15, ge=1, le=90),
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """
    Lista créditos próximos a expirar (solo RRHH/Admin).
    """
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    return {"dias_alerta": dias_alerta, "expiraciones": []}
