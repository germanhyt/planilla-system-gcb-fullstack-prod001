"""Sprint 3: Consultas de banco de horas compensatorias."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..banco_horas import (
    get_saldo_actual,
    historial_trabajador,
    listar_proximas_expiraciones,
)
from ..db import get_db
from ..deps import get_current_user
from ..models import Usuario

router = APIRouter(prefix="/banco-horas", tags=["banco_horas"])


@router.get("/saldo/{trabajador_id}")
async def consultar_saldo(
    trabajador_id: int,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Consulta saldo actual de horas compensatorias.
    Trabajador: solo su propio saldo. Jefe/RRHH/Admin: cualquier trabajador (con filtro de unidad para jefe).
    """
    if user.rol == "trabajador":
        from sqlalchemy import select
        from ..models import Trabajador
        q = select(Trabajador).where(Trabajador.usuario_id == user.id)
        result = await db.execute(q)
        mi_trab = result.scalar_one_or_none()
        if not mi_trab or mi_trab.id != trabajador_id:
            raise HTTPException(403, "Solo puede ver su propio saldo")
    
    if user.rol == "jefe":
        from sqlalchemy import select
        from ..models import Trabajador
        q = select(Trabajador).where(Trabajador.id == trabajador_id)
        result = await db.execute(q)
        trab = result.scalar_one_or_none()
        if not trab or trab.unidad_id != user.unidad_id:
            raise HTTPException(403, "Solo puede ver trabajadores de su unidad")
    
    saldo = await get_saldo_actual(db, trabajador_id)
    return {"trabajador_id": trabajador_id, "saldo_horas": saldo}


@router.get("/historial/{trabajador_id}")
async def consultar_historial(
    trabajador_id: int,
    limite: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Historial de movimientos de horas compensatorias.
    """
    if user.rol == "trabajador":
        from sqlalchemy import select
        from ..models import Trabajador
        q = select(Trabajador).where(Trabajador.usuario_id == user.id)
        result = await db.execute(q)
        mi_trab = result.scalar_one_or_none()
        if not mi_trab or mi_trab.id != trabajador_id:
            raise HTTPException(403, "Solo puede ver su propio historial")
    
    if user.rol == "jefe":
        from sqlalchemy import select
        from ..models import Trabajador
        q = select(Trabajador).where(Trabajador.id == trabajador_id)
        result = await db.execute(q)
        trab = result.scalar_one_or_none()
        if not trab or trab.unidad_id != user.unidad_id:
            raise HTTPException(403, "Solo puede ver trabajadores de su unidad")
    
    movimientos = await historial_trabajador(db, trabajador_id, limite)
    return {"trabajador_id": trabajador_id, "movimientos": movimientos}


@router.get("/expiraciones")
async def proximas_expiraciones(
    dias_alerta: int = Query(15, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Lista créditos próximos a expirar (solo RRHH/Admin).
    """
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    expiraciones = await listar_proximas_expiraciones(db, dias_alerta)
    return {"dias_alerta": dias_alerta, "expiraciones": expiraciones}
