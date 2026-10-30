"""Sprint 3: Dashboard de excepciones y alertas."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Asistencia, HorarioPlan, Marca, Trabajador, Usuario
from ..schemas import FaltaJustificadaIn

router = APIRouter(prefix="/excepciones", tags=["excepciones"])


@router.get("/faltas-sin-justificar")
def listar_faltas_sin_justificar(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    unidad_id: int | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Faltas sin justificar (días programados sin asistencia registrada)."""
    if user.rol == "trabajador":
        raise HTTPException(403, "No autorizado")
    
    # Parse periodo
    anio, mes = map(int, periodo.split("-"))
    fecha_inicio = date(anio, mes, 1)
    if mes == 12:
        fecha_fin = date(anio + 1, 1, 1)
    else:
        fecha_fin = date(anio, mes + 1, 1)
    
    # Filtrar trabajadores según rol y unidad
    query = db.query(Trabajador)
    if user.rol == "jefe":
        if not user.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        query = query.filter(Trabajador.unidad_id == user.unidad_id)
    elif unidad_id:
        query = query.filter(Trabajador.unidad_id == unidad_id)
    
    trabajadores = query.all()
    faltas = []
    
    for trab in trabajadores:
        # Obtener días con horario programado
        dia_actual = fecha_inicio
        while dia_actual < fecha_fin:
            # Verificar si tiene plan de horario para ese día
            dia_inicio_semana = dia_actual - timedelta(days=dia_actual.weekday())
            plan = db.query(HorarioPlan).filter(
                and_(
                    HorarioPlan.trabajador_id == trab.id,
                    HorarioPlan.semana_inicio == dia_inicio_semana
                )
            ).order_by(HorarioPlan.version.desc()).first()
            
            if plan:
                dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
                dia_semana = dias[dia_actual.weekday()]
                plantilla_id = getattr(plan, f"{dia_semana}_plantilla_id", None)
                
                if plantilla_id:
                    # Día programado, verificar si hay asistencia
                    asistencia = db.query(Asistencia).filter(
                        and_(
                            Asistencia.trabajador_id == trab.id,
                            Asistencia.dia_operativo == dia_actual
                        )
                    ).first()
                    
                    if not asistencia:
                        faltas.append({
                            "trabajador_id": trab.id,
                            "codigo": trab.codigo,
                            "nombres": trab.nombres,
                            "apellidos": trab.apellidos,
                            "dia": dia_actual.isoformat(),
                            "justificada": False  # TODO: link to justifications table
                        })
            
            dia_actual += timedelta(days=1)
    
    return faltas


@router.get("/tardanzas-recurrentes")
def listar_tardanzas_recurrentes(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    min_tardanzas: int = Query(3, ge=1),
    unidad_id: int | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Trabajadores con tardanzas recurrentes (>= min_tardanzas en el periodo)."""
    if user.rol == "trabajador":
        raise HTTPException(403, "No autorizado")
    
    # Filtrar trabajadores según rol y unidad
    query = db.query(
        Asistencia.trabajador_id,
        func.count(Asistencia.id).label("cant_tardanzas"),
        func.sum(Asistencia.tardanza_min).label("total_min_tardanza")
    ).filter(
        and_(
            Asistencia.periodo == periodo,
            Asistencia.tardanza_min > 0
        )
    ).group_by(Asistencia.trabajador_id).having(
        func.count(Asistencia.id) >= min_tardanzas
    )
    
    if user.rol == "jefe":
        if not user.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        query = query.join(Trabajador).filter(Trabajador.unidad_id == user.unidad_id)
    elif unidad_id:
        query = query.join(Trabajador).filter(Trabajador.unidad_id == unidad_id)
    
    resultados = query.all()
    
    tardanzas_recurrentes = []
    for r in resultados:
        trab = db.query(Trabajador).get(r.trabajador_id)
        if trab:
            tardanzas_recurrentes.append({
                "trabajador_id": trab.id,
                "codigo": trab.codigo,
                "nombres": trab.nombres,
                "apellidos": trab.apellidos,
                "cantidad_tardanzas": r.cant_tardanzas,
                "total_minutos": int(r.total_min_tardanza)
            })
    
    return tardanzas_recurrentes


@router.get("/marcas-fuera-geocerca")
def listar_marcas_fuera_geocerca(
    desde: date = Query(...),
    hasta: date = Query(...),
    unidad_id: int | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Marcas registradas fuera de la geocerca configurada."""
    if user.rol == "trabajador":
        raise HTTPException(403, "No autorizado")
    
    # Obtener marcas con distancia > 0 (fuera de geocerca)
    query = db.query(Marca).join(Trabajador).filter(
        and_(
            Marca.ts_servidor >= desde,
            Marca.ts_servidor < hasta + timedelta(days=1),
            Marca.distancia_m.isnot(None),
            Marca.distancia_m > 200  # Umbral configurable
        )
    )
    
    if user.rol == "jefe":
        if not user.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        query = query.filter(Trabajador.unidad_id == user.unidad_id)
    elif unidad_id:
        query = query.filter(Trabajador.unidad_id == unidad_id)
    
    marcas = query.order_by(Marca.ts_servidor.desc()).limit(200).all()
    
    resultado = []
    for m in marcas:
        trab = db.query(Trabajador).get(m.trabajador_id)
        if trab:
            resultado.append({
                "marca_id": m.id,
                "trabajador_id": trab.id,
                "codigo": trab.codigo,
                "nombres": trab.nombres,
                "apellidos": trab.apellidos,
                "timestamp": m.ts_servidor.isoformat(),
                "tipo": m.tipo,
                "latitud": float(m.lat) if m.lat else None,
                "longitud": float(m.lng) if m.lng else None,
                "distancia_metros": int(m.distancia_m) if m.distancia_m else None
            })
    
    return resultado


@router.get("/part-time-riesgo")
def reporte_part_time_riesgo(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Part-time (PT85/PT102) con promedio semanal > umbral (4 h) por día TRABAJADO.

    Criterio unificado con la bandeja: promedio = horas de la semana (lun-dom) / días con asistencia.
    La alerta es informativa: no bloquea marcas, cálculo ni cierre.
    """
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    from sqlalchemy import true

    from .bandeja import alertas_pt

    anio, mes = map(int, periodo.split("-"))
    desde = date(anio, mes, 1)
    hasta = (date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)) - timedelta(days=1)
    return [{
        "trabajador_id": a["trabajador"].id,
        "codigo": a["trabajador"].codigo,
        "nombres": a["trabajador"].nombres,
        "apellidos": a["trabajador"].apellidos,
        "semana_inicio": a["semana"].isoformat(),
        "dias_trabajados": a["dias"],
        "total_horas_semana": a["total"],
        "promedio_diario": a["promedio"],
        "umbral": a["umbral"],
        "criterio": "horas_semana / dias_trabajados",
        "bloqueante": False,
        "tipo_contrato": a["contrato"],
    } for a in sorted(alertas_pt(db, true(), desde, hasta), key=lambda x: (x["semana"], x["trabajador"].codigo))]


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
