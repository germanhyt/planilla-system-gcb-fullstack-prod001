"""Sprint 3: Cierre y reapertura de periodos contables."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import auditar
from ..db import get_db
from ..deps import get_current_user
from ..models import Asistencia, CierrePeriodo, Empresa, Usuario
from ..schemas import CierrePeriodoIn, ReaperturaPeriodoIn

router = APIRouter(prefix="/periodos", tags=["periodos"])


@router.post("/cerrar")
async def cerrar_periodo(
    data: CierrePeriodoIn,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Cerrar periodo mensual. Solo RRHH/Admin.
    Bloquea recálculo y marcas retroactivas del periodo.
    """
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado para cerrar periodos")
    
    q = select(Empresa).where(Empresa.id == data.empresa_id)
    result = await db.execute(q)
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(404, "Empresa no encontrada")
    
    q_existe = select(CierrePeriodo).where(
        and_(
            CierrePeriodo.empresa_id == data.empresa_id,
            CierrePeriodo.periodo == data.periodo,
            CierrePeriodo.estado == "cerrado",
        )
    )
    result = await db.execute(q_existe)
    if result.scalar_one_or_none():
        raise HTTPException(400, f"Periodo {data.periodo} ya está cerrado para esta empresa")
    
    cierre = CierrePeriodo(
        empresa_id=data.empresa_id,
        periodo=data.periodo,
        cerrado_por=user.id,
        estado="cerrado",
    )
    db.add(cierre)
    
    stmt = (
        update(Asistencia)
        .where(
            and_(
                Asistencia.periodo == data.periodo,
                Asistencia.trabajador_id.in_(
                    select(Asistencia.trabajador_id)
                    .join(Asistencia.trabajador)
                    .where(Asistencia.trabajador.has(empresa_id=data.empresa_id))
                ),
            )
        )
        .values(periodo_cerrado=True)
    )
    await db.execute(stmt)
    
    await db.commit()
    await db.refresh(cierre)
    
    await auditar(
        db,
        usuario_id=user.id,
        accion="cerrar_periodo",
        entidad="cierre_periodo",
        entidad_id=str(cierre.id),
        despues={"empresa_id": data.empresa_id, "periodo": data.periodo},
    )
    
    return {
        "id": cierre.id,
        "empresa_id": cierre.empresa_id,
        "periodo": cierre.periodo,
        "cerrado_por": cierre.cerrado_por,
        "cerrado_en": cierre.cerrado_en.isoformat(),
        "estado": cierre.estado,
    }


@router.post("/reabrir/{cierre_id}")
async def reabrir_periodo(
    cierre_id: int,
    data: ReaperturaPeriodoIn,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Reabrir periodo cerrado. Solo Admin con razón obligatoria.
    """
    if user.rol != "admin":
        raise HTTPException(403, "Solo admin puede reabrir periodos")
    
    q = select(CierrePeriodo).where(CierrePeriodo.id == cierre_id)
    result = await db.execute(q)
    cierre = result.scalar_one_or_none()
    if not cierre:
        raise HTTPException(404, "Cierre de periodo no encontrado")
    
    if cierre.estado != "cerrado":
        raise HTTPException(400, "Periodo no está cerrado")
    
    cierre.estado = "reabierto"
    cierre.reabierto_por = user.id
    cierre.reabierto_en = datetime.now()
    cierre.razon_reapertura = data.razon_reapertura
    
    stmt = (
        update(Asistencia)
        .where(
            and_(
                Asistencia.periodo == cierre.periodo,
                Asistencia.trabajador_id.in_(
                    select(Asistencia.trabajador_id)
                    .join(Asistencia.trabajador)
                    .where(Asistencia.trabajador.has(empresa_id=cierre.empresa_id))
                ),
            )
        )
        .values(periodo_cerrado=False)
    )
    await db.execute(stmt)
    
    await db.commit()
    
    await auditar(
        db,
        usuario_id=user.id,
        accion="reabrir_periodo",
        entidad="cierre_periodo",
        entidad_id=str(cierre.id),
        antes={"estado": "cerrado"},
        despues={"estado": "reabierto", "razon": data.razon_reapertura},
    )
    
    return {
        "id": cierre.id,
        "empresa_id": cierre.empresa_id,
        "periodo": cierre.periodo,
        "estado": cierre.estado,
        "reabierto_por": cierre.reabierto_por,
        "reabierto_en": cierre.reabierto_en.isoformat(),
        "razon_reapertura": cierre.razon_reapertura,
    }


@router.get("/historial")
async def historial_cierres(
    empresa_id: int = None,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Listar histórico de cierres de periodo.
    RRHH/Admin: todos. Jefe: no autorizado.
    """
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    q = select(CierrePeriodo).order_by(CierrePeriodo.cerrado_en.desc())
    if empresa_id:
        q = q.where(CierrePeriodo.empresa_id == empresa_id)
    
    result = await db.execute(q)
    cierres = result.scalars().all()
    
    return [
        {
            "id": c.id,
            "empresa_id": c.empresa_id,
            "periodo": c.periodo,
            "cerrado_por": c.cerrado_por,
            "cerrado_en": c.cerrado_en.isoformat(),
            "reabierto_por": c.reabierto_por,
            "reabierto_en": c.reabierto_en.isoformat() if c.reabierto_en else None,
            "razon_reapertura": c.razon_reapertura,
            "estado": c.estado,
        }
        for c in cierres
    ]
