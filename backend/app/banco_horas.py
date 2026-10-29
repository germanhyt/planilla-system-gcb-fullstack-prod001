"""Sprint 3: Gestión de banco de horas compensatorias."""
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import BancoHorasCompensatorias, Trabajador


async def get_saldo_actual(db: AsyncSession, trabajador_id: int) -> float:
    """Obtiene el saldo actual de horas compensatorias del trabajador."""
    q = (
        select(BancoHorasCompensatorias)
        .where(BancoHorasCompensatorias.trabajador_id == trabajador_id)
        .order_by(BancoHorasCompensatorias.fecha_movimiento.desc(), BancoHorasCompensatorias.id.desc())
        .limit(1)
    )
    result = await db.execute(q)
    ultimo = result.scalar_one_or_none()
    return float(ultimo.saldo_nuevo) if ultimo else 0.0


async def registrar_credito(
    db: AsyncSession,
    trabajador_id: int,
    horas: float,
    origen: str,
    regularizacion_id: Optional[int] = None,
    dias_expiracion: int = 90,
    fecha_movimiento: Optional[date] = None,
) -> BancoHorasCompensatorias:
    """
    Registra crédito de horas compensatorias.
    Por defecto expiran en 90 días.
    """
    if fecha_movimiento is None:
        fecha_movimiento = date.today()
    
    saldo_anterior = await get_saldo_actual(db, trabajador_id)
    saldo_nuevo = saldo_anterior + horas
    
    movimiento = BancoHorasCompensatorias(
        trabajador_id=trabajador_id,
        fecha_movimiento=fecha_movimiento,
        tipo="credito",
        horas=horas,
        saldo_anterior=saldo_anterior,
        saldo_nuevo=saldo_nuevo,
        origen=origen,
        regularizacion_id=regularizacion_id,
        dias_expiracion=dias_expiracion,
        fecha_expira=fecha_movimiento + timedelta(days=dias_expiracion),
    )
    db.add(movimiento)
    await db.flush()
    return movimiento


async def registrar_debito(
    db: AsyncSession,
    trabajador_id: int,
    horas: float,
    origen: str,
    asistencia_id: Optional[int] = None,
    fecha_movimiento: Optional[date] = None,
) -> BancoHorasCompensatorias:
    """
    Registra débito de horas compensatorias (descanso tomado).
    """
    if fecha_movimiento is None:
        fecha_movimiento = date.today()
    
    saldo_anterior = await get_saldo_actual(db, trabajador_id)
    if saldo_anterior < horas:
        raise ValueError(f"Saldo insuficiente. Disponible: {saldo_anterior:.2f}h, solicitado: {horas:.2f}h")
    
    saldo_nuevo = saldo_anterior - horas
    
    movimiento = BancoHorasCompensatorias(
        trabajador_id=trabajador_id,
        fecha_movimiento=fecha_movimiento,
        tipo="debito",
        horas=horas,
        saldo_anterior=saldo_anterior,
        saldo_nuevo=saldo_nuevo,
        origen=origen,
        asistencia_id=asistencia_id,
    )
    db.add(movimiento)
    await db.flush()
    return movimiento


async def listar_proximas_expiraciones(
    db: AsyncSession, dias_alerta: int = 15
) -> list[dict]:
    """
    Lista créditos próximos a expirar (dentro de N días).
    """
    hoy = date.today()
    fecha_limite = hoy + timedelta(days=dias_alerta)
    
    q = (
        select(BancoHorasCompensatorias, Trabajador)
        .join(Trabajador, BancoHorasCompensatorias.trabajador_id == Trabajador.id)
        .where(
            and_(
                BancoHorasCompensatorias.tipo == "credito",
                BancoHorasCompensatorias.fecha_expira.isnot(None),
                BancoHorasCompensatorias.fecha_expira >= hoy,
                BancoHorasCompensatorias.fecha_expira <= fecha_limite,
            )
        )
        .order_by(BancoHorasCompensatorias.fecha_expira)
    )
    
    result = await db.execute(q)
    rows = result.all()
    
    return [
        {
            "trabajador_id": trab.id,
            "trabajador_codigo": trab.codigo,
            "trabajador_nombre": f"{trab.nombres} {trab.apellidos}",
            "horas": float(mov.horas),
            "fecha_expira": mov.fecha_expira.isoformat(),
            "dias_restantes": (mov.fecha_expira - hoy).days,
        }
        for mov, trab in rows
    ]


async def historial_trabajador(
    db: AsyncSession, trabajador_id: int, limite: int = 50
) -> list[dict]:
    """
    Historial de movimientos de un trabajador.
    """
    q = (
        select(BancoHorasCompensatorias)
        .where(BancoHorasCompensatorias.trabajador_id == trabajador_id)
        .order_by(BancoHorasCompensatorias.fecha_movimiento.desc(), BancoHorasCompensatorias.id.desc())
        .limit(limite)
    )
    result = await db.execute(q)
    movimientos = result.scalars().all()
    
    return [
        {
            "id": m.id,
            "fecha_movimiento": m.fecha_movimiento.isoformat(),
            "tipo": m.tipo,
            "horas": float(m.horas),
            "saldo_anterior": float(m.saldo_anterior),
            "saldo_nuevo": float(m.saldo_nuevo),
            "origen": m.origen,
            "fecha_expira": m.fecha_expira.isoformat() if m.fecha_expira else None,
            "creado_en": m.creado_en.isoformat(),
        }
        for m in movimientos
    ]
