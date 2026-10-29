"""Sprint 3: Dashboard de excepciones y alertas."""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import auditar
from ..db import get_db
from ..deps import get_current_user
from ..models import Asistencia, FaltaJustificada, HorarioPlan, Marca, Trabajador, TipoContrato, Unidad, Usuario
from ..schemas import FaltaJustificadaIn

router = APIRouter(prefix="/excepciones", tags=["excepciones"])


@router.get("/faltas-sin-justificar")
async def listar_faltas_sin_justificar(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    unidad_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Días sin marca (entrada o salida) con horario programado.
    Jefe: solo su unidad. RRHH/Admin: filtrable por unidad.
    """
    if user.rol == "trabajador":
        raise HTTPException(403, "No autorizado")
    
    if user.rol == "jefe":
        if not user.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        unidad_id = user.unidad_id
    
    año, mes = periodo.split("-")
    año = int(año)
    mes = int(mes)
    
    if mes == 12:
        fin_mes = date(año + 1, 1, 1) - timedelta(days=1)
    else:
        fin_mes = date(año, mes + 1, 1) - timedelta(days=1)
    inicio_mes = date(año, mes, 1)
    
    q = (
        select(Asistencia, Trabajador, Unidad)
        .join(Trabajador, Asistencia.trabajador_id == Trabajador.id)
        .join(Unidad, Trabajador.unidad_id == Unidad.id)
        .where(
            and_(
                Asistencia.periodo == periodo,
                or_(
                    Asistencia.entrada_marca_id.is_(None),
                    Asistencia.salida_marca_id.is_(None),
                ),
                Asistencia.turno_plantilla_id.isnot(None),
            )
        )
    )
    
    if unidad_id:
        q = q.where(Unidad.id == unidad_id)
    
    q = q.order_by(Asistencia.dia_operativo, Trabajador.codigo)
    result = await db.execute(q)
    faltas = result.all()
    
    q_just = select(FaltaJustificada.dia, FaltaJustificada.trabajador_id).where(
        and_(
            FaltaJustificada.dia >= inicio_mes,
            FaltaJustificada.dia <= fin_mes,
        )
    )
    just_result = await db.execute(q_just)
    justificadas = {(dia, tid) for dia, tid in just_result.all()}
    
    excepciones = []
    for asist, trab, uni in faltas:
        if (asist.dia_operativo, trab.id) not in justificadas:
            excepciones.append({
                "trabajador_id": trab.id,
                "trabajador_codigo": trab.codigo,
                "trabajador_nombre": f"{trab.nombres} {trab.apellidos}",
                "unidad": uni.nombre,
                "dia": asist.dia_operativo.isoformat(),
                "tiene_entrada": asist.entrada_marca_id is not None,
                "tiene_salida": asist.salida_marca_id is not None,
            })
    
    return excepciones


@router.get("/tardanzas-recurrentes")
async def listar_tardanzas_recurrentes(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    min_tardanzas: int = Query(3, ge=1),
    unidad_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Trabajadores con ≥N tardanzas en el mes.
    """
    if user.rol == "trabajador":
        raise HTTPException(403, "No autorizado")
    
    if user.rol == "jefe":
        if not user.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        unidad_id = user.unidad_id
    
    q = (
        select(
            Trabajador,
            Unidad,
            func.count(Asistencia.id).label("total_tardanzas"),
            func.sum(Asistencia.tardanza_min).label("minutos_acumulados"),
        )
        .join(Asistencia, Trabajador.id == Asistencia.trabajador_id)
        .join(Unidad, Trabajador.unidad_id == Unidad.id)
        .where(
            and_(
                Asistencia.periodo == periodo,
                Asistencia.tardanza_min > 0,
            )
        )
        .group_by(Trabajador.id, Unidad.id)
        .having(func.count(Asistencia.id) >= min_tardanzas)
    )
    
    if unidad_id:
        q = q.where(Unidad.id == unidad_id)
    
    q = q.order_by(func.count(Asistencia.id).desc())
    result = await db.execute(q)
    tardanzas = result.all()
    
    return [
        {
            "trabajador_id": trab.id,
            "trabajador_codigo": trab.codigo,
            "trabajador_nombre": f"{trab.nombres} {trab.apellidos}",
            "unidad": uni.nombre,
            "total_tardanzas": total,
            "minutos_acumulados": int(minutos),
        }
        for trab, uni, total, minutos in tardanzas
    ]


@router.get("/marcas-fuera-geocerca")
async def listar_marcas_fuera_geocerca(
    desde: date = Query(...),
    hasta: date = Query(...),
    unidad_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Marcas con validación fuera_geocerca.
    """
    if user.rol == "trabajador":
        raise HTTPException(403, "No autorizado")
    
    if user.rol == "jefe":
        if not user.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        unidad_id = user.unidad_id
    
    q = (
        select(Marca, Trabajador, Unidad)
        .join(Trabajador, Marca.trabajador_id == Trabajador.id)
        .join(Unidad, Trabajador.unidad_id == Unidad.id)
        .where(
            and_(
                Marca.validacion_estado == "fuera_geocerca",
                func.date(Marca.ts_servidor) >= desde,
                func.date(Marca.ts_servidor) <= hasta,
            )
        )
    )
    
    if unidad_id:
        q = q.where(Unidad.id == unidad_id)
    
    q = q.order_by(Marca.ts_servidor.desc())
    result = await db.execute(q)
    marcas = result.all()
    
    return [
        {
            "marca_id": marca.id,
            "trabajador_codigo": trab.codigo,
            "trabajador_nombre": f"{trab.nombres} {trab.apellidos}",
            "unidad": uni.nombre,
            "tipo": marca.tipo,
            "ts_servidor": marca.ts_servidor.isoformat(),
            "distancia_m": float(marca.distancia_m) if marca.distancia_m else None,
            "lat": float(marca.lat) if marca.lat else None,
            "lng": float(marca.lng) if marca.lng else None,
        }
        for marca, trab, uni in marcas
    ]


@router.get("/part-time-riesgo")
async def reporte_part_time_riesgo(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Trabajadores PT con promedio >4h/día en el mes (riesgo normativo).
    """
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    q = (
        select(
            Trabajador,
            TipoContrato,
            func.sum(Asistencia.horas_trabajadas).label("total_horas"),
            func.count(Asistencia.id).label("dias_trabajados"),
        )
        .join(Asistencia, Trabajador.id == Asistencia.trabajador_id)
        .join(TipoContrato, Trabajador.tipo_contrato_id == TipoContrato.id)
        .where(
            and_(
                Asistencia.periodo == periodo,
                TipoContrato.es_part_time == True,
            )
        )
        .group_by(Trabajador.id, TipoContrato.id)
    )
    
    result = await db.execute(q)
    rows = result.all()
    
    riesgo = []
    for trab, contrato, total_h, dias in rows:
        promedio = float(total_h) / dias if dias > 0 else 0
        if promedio > 4.0:
            riesgo.append({
                "trabajador_id": trab.id,
                "trabajador_codigo": trab.codigo,
                "trabajador_nombre": f"{trab.nombres} {trab.apellidos}",
                "tipo_contrato": contrato.nombre,
                "horas_mes": contrato.horas_mes,
                "dias_trabajados": dias,
                "total_horas": float(total_h),
                "promedio_diario": round(promedio, 2),
            })
    
    return riesgo


@router.post("/justificar-falta")
async def justificar_falta(
    data: FaltaJustificadaIn,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Jefe/RRHH justifica falta de trabajador.
    """
    if user.rol not in ("jefe", "rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    q = select(Trabajador).where(Trabajador.id == data.trabajador_id)
    result = await db.execute(q)
    trab = result.scalar_one_or_none()
    if not trab:
        raise HTTPException(404, "Trabajador no encontrado")
    
    if user.rol == "jefe":
        if not user.unidad_id or trab.unidad_id != user.unidad_id:
            raise HTTPException(403, "Trabajador no pertenece a tu unidad")
    
    q_existe = select(FaltaJustificada).where(
        and_(
            FaltaJustificada.trabajador_id == data.trabajador_id,
            FaltaJustificada.dia == data.dia,
        )
    )
    result = await db.execute(q_existe)
    if result.scalar_one_or_none():
        raise HTTPException(400, "Falta ya justificada para este día")
    
    justif = FaltaJustificada(
        trabajador_id=data.trabajador_id,
        dia=data.dia,
        motivo=data.motivo,
        descripcion=data.descripcion,
        adjunto_url=data.adjunto_url,
        justificado_por=user.id,
    )
    db.add(justif)
    await db.commit()
    await db.refresh(justif)
    
    await auditar(
        db,
        usuario_id=user.id,
        accion="justificar_falta",
        entidad="falta_justificada",
        entidad_id=str(justif.id),
        despues={"trabajador_id": data.trabajador_id, "dia": data.dia.isoformat(), "motivo": data.motivo},
    )
    
    return {
        "id": justif.id,
        "trabajador_id": justif.trabajador_id,
        "dia": justif.dia.isoformat(),
        "motivo": justif.motivo,
        "justificado_por": justif.justificado_por,
        "creado_en": justif.creado_en.isoformat(),
    }
