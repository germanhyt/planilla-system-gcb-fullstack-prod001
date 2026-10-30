"""Sprint 3: Consultas de banco de horas compensatorias."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import BancoHorasCompensatorias, Trabajador, Usuario

router = APIRouter(prefix="/banco-horas", tags=["banco_horas"])


class RegistrarDescansoIn(BaseModel):
    trabajador_id: int
    fecha: date
    horas: float
    asistencia_id: int


def crear_movimiento_banco(
    db: Session,
    trabajador_id: int,
    fecha: date,
    tipo: str,
    horas: float,
    origen: str,
    regularizacion_id: int = None,
    asistencia_id: int = None,
    dias_expiracion: int = None
) -> BancoHorasCompensatorias:
    """Helper para crear un movimiento en el banco de horas."""
    # Obtener saldo actual
    ultimo = db.query(BancoHorasCompensatorias).filter(
        BancoHorasCompensatorias.trabajador_id == trabajador_id
    ).order_by(BancoHorasCompensatorias.creado_en.desc(), BancoHorasCompensatorias.id.desc()).first()
    
    saldo_anterior = float(ultimo.saldo_nuevo) if ultimo else 0.0
    
    if tipo == "credito":
        saldo_nuevo = saldo_anterior + horas
    else:  # debito
        if saldo_anterior < horas:
            raise ValueError(f"Saldo insuficiente: {saldo_anterior} < {horas}")
        saldo_nuevo = saldo_anterior - horas
    
    fecha_expira = None
    if tipo == "credito" and dias_expiracion:
        fecha_expira = fecha + timedelta(days=dias_expiracion)
    
    movimiento = BancoHorasCompensatorias(
        trabajador_id=trabajador_id,
        fecha_movimiento=fecha,
        tipo=tipo,
        horas=horas,
        saldo_anterior=saldo_anterior,
        saldo_nuevo=saldo_nuevo,
        origen=origen,
        regularizacion_id=regularizacion_id,
        asistencia_id=asistencia_id,
        dias_expiracion=dias_expiracion,
        fecha_expira=fecha_expira
    )
    db.add(movimiento)
    return movimiento


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
    
    # Obtener último movimiento para saldo actual
    ultimo = db.query(BancoHorasCompensatorias).filter(
        BancoHorasCompensatorias.trabajador_id == trabajador_id
    ).order_by(BancoHorasCompensatorias.creado_en.desc(), BancoHorasCompensatorias.id.desc()).first()
    
    saldo = ultimo.saldo_nuevo if ultimo else 0.0
    
    return {"trabajador_id": trabajador_id, "saldo_horas": float(saldo)}


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
    
    movimientos = db.query(BancoHorasCompensatorias).filter(
        BancoHorasCompensatorias.trabajador_id == trabajador_id
    ).order_by(BancoHorasCompensatorias.creado_en.desc(), BancoHorasCompensatorias.id.desc()).limit(limite).all()
    
    return {
        "trabajador_id": trabajador_id,
        "movimientos": [
            {
                "id": m.id,
                "fecha_movimiento": m.fecha_movimiento.isoformat(),
                "tipo": m.tipo,
                "horas": float(m.horas),
                "saldo_anterior": float(m.saldo_anterior),
                "saldo_nuevo": float(m.saldo_nuevo),
                "origen": m.origen,
                "fecha_expira": m.fecha_expira.isoformat() if m.fecha_expira else None,
                "creado_en": m.creado_en.isoformat()
            }
            for m in movimientos
        ]
    }


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
    
    hoy = date.today()
    fecha_limite = hoy + timedelta(days=dias_alerta)
    
    # Obtener créditos con fecha_expira dentro del rango de alerta
    creditos = db.query(BancoHorasCompensatorias).filter(
        and_(
            BancoHorasCompensatorias.tipo == "credito",
            BancoHorasCompensatorias.fecha_expira.isnot(None),
            BancoHorasCompensatorias.fecha_expira <= fecha_limite,
            BancoHorasCompensatorias.fecha_expira >= hoy
        )
    ).order_by(BancoHorasCompensatorias.fecha_expira).all()
    
    return {
        "dias_alerta": dias_alerta,
        "expiraciones": [
            {
                "id": c.id,
                "trabajador_id": c.trabajador_id,
                "horas": float(c.horas),
                "fecha_expira": c.fecha_expira.isoformat(),
                "dias_restantes": (c.fecha_expira - hoy).days,
                "origen": c.origen
            }
            for c in creditos
        ]
    }


@router.post("/registrar-descanso")
def registrar_descanso(
    data: RegistrarDescansoIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """
    Registra descanso compensatorio tomado (débito). Solo jefe/rrhh/admin.
    """
    if user.rol not in ("jefe", "rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    if user.rol == "jefe":
        trab = db.query(Trabajador).filter(Trabajador.id == data.trabajador_id).first()
        if not trab or trab.unidad_id != user.unidad_id:
            raise HTTPException(403, "Solo puede registrar descansos de su unidad")
    
    try:
        movimiento = crear_movimiento_banco(
            db,
            trabajador_id=data.trabajador_id,
            fecha=data.fecha,
            tipo="debito",
            horas=data.horas,
            origen=f"Descanso compensatorio tomado - registrado por {user.email}",
            asistencia_id=data.asistencia_id
        )
        db.commit()
        
        return {
            "id": movimiento.id,
            "trabajador_id": movimiento.trabajador_id,
            "tipo": movimiento.tipo,
            "horas": float(movimiento.horas),
            "saldo_nuevo": float(movimiento.saldo_nuevo),
            "fecha_movimiento": movimiento.fecha_movimiento.isoformat()
        }
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e)) from None
