"""API de horarios semanales versionados. Sprint 2."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..audit import audit
from ..db import get_db
from ..deps import require_role
from ..models import HorarioPlan, Trabajador, TurnoPlantilla, Usuario
from ..schemas import HorarioPlanIn

r = APIRouter(prefix="/horarios", tags=["horarios"])


def validar_alertas(db: Session, plan_in: HorarioPlanIn) -> dict:
    """Valida alertas no bloqueantes: >8h/día, >48h/semana, falta descanso 24h."""
    alertas = {"warnings": []}
    
    trabajador = db.query(Trabajador).get(plan_in.trabajador_id)
    if not trabajador:
        return alertas
    
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    total_semanal_min = 0
    horas_por_dia = []
    
    for dia in dias:
        plantilla_id = getattr(plan_in, f"{dia}_plantilla_id", None)
        if plantilla_id:
            plantilla = db.query(TurnoPlantilla).get(plantilla_id)
            if plantilla:
                inicio_min = plantilla.inicio.hour * 60 + plantilla.inicio.minute
                fin_min = plantilla.fin.hour * 60 + plantilla.fin.minute
                
                if fin_min < inicio_min:
                    fin_min += 1440
                
                duracion_min = fin_min - inicio_min - plantilla.refrigerio_min
                horas_por_dia.append(duracion_min / 60)
                total_semanal_min += duracion_min
            else:
                horas_por_dia.append(0)
        else:
            horas_por_dia.append(0)
    
    for i, horas in enumerate(horas_por_dia):
        if horas > 8:
            alertas["warnings"].append(f"{dias[i].capitalize()}: {horas:.1f}h excede 8h/día")
    
    total_semanal_h = total_semanal_min / 60
    if total_semanal_h > 48:
        alertas["warnings"].append(f"Total semanal {total_semanal_h:.1f}h excede 48h/semana")
    
    dias_trabajados = sum(1 for h in horas_por_dia if h > 0)
    if dias_trabajados == 7:
        alertas["warnings"].append("No hay descanso semanal de 24h")
    
    return alertas


@r.post("/")
def crear_horario(plan_in: HorarioPlanIn, db: Session = Depends(get_db), u: Usuario = Depends(require_role("jefe"))):
    trabajador = db.query(Trabajador).get(plan_in.trabajador_id)
    if not trabajador:
        raise HTTPException(404, "Trabajador no encontrado")
    
    if u.rol == "jefe" and trabajador.unidad_id != u.unidad_id:
        raise HTTPException(403, "Solo puede programar trabajadores de su unidad")
    
    semana_inicio = plan_in.semana_inicio
    if semana_inicio.weekday() != 0:
        semana_inicio = semana_inicio - timedelta(days=semana_inicio.weekday())
    
    ultimo = db.query(HorarioPlan).filter(
        and_(
            HorarioPlan.trabajador_id == plan_in.trabajador_id,
            HorarioPlan.semana_inicio == semana_inicio
        )
    ).order_by(HorarioPlan.version.desc()).first()
    
    nueva_version = (ultimo.version + 1) if ultimo else 1
    
    alertas = validar_alertas(db, plan_in)
    
    plan = HorarioPlan(
        trabajador_id=plan_in.trabajador_id,
        semana_inicio=semana_inicio,
        version=nueva_version,
        lunes_plantilla_id=plan_in.lunes_plantilla_id,
        martes_plantilla_id=plan_in.martes_plantilla_id,
        miercoles_plantilla_id=plan_in.miercoles_plantilla_id,
        jueves_plantilla_id=plan_in.jueves_plantilla_id,
        viernes_plantilla_id=plan_in.viernes_plantilla_id,
        sabado_plantilla_id=plan_in.sabado_plantilla_id,
        domingo_plantilla_id=plan_in.domingo_plantilla_id,
        alertas=alertas,
        creado_por=u.id
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    
    audit(db, u.id, "crear", "horario_plan", str(plan.id), None, {
        "trabajador_id": plan.trabajador_id,
        "semana_inicio": str(semana_inicio),
        "version": nueva_version
    })
    
    return {"id": plan.id, "version": nueva_version, "alertas": alertas}


@r.get("/trabajador/{trabajador_id}")
def listar_horarios(trabajador_id: int, db: Session = Depends(get_db), u: Usuario = Depends(require_role("trabajador"))):
    trabajador = db.query(Trabajador).get(trabajador_id)
    if not trabajador:
        raise HTTPException(404, "Trabajador no encontrado")
    
    if u.rol == "trabajador" and trabajador.usuario_id != u.id:
        raise HTTPException(403, "Solo puede ver sus propios horarios")
    
    if u.rol == "jefe" and trabajador.unidad_id != u.unidad_id:
        raise HTTPException(403, "Solo puede ver trabajadores de su unidad")
    
    planes = db.query(HorarioPlan).filter(
        HorarioPlan.trabajador_id == trabajador_id
    ).order_by(HorarioPlan.semana_inicio.desc(), HorarioPlan.version.desc()).limit(20).all()
    
    return [{"id": p.id, "semana_inicio": str(p.semana_inicio), "version": p.version, "alertas": p.alertas} for p in planes]


@r.post("/copiar-semana-anterior")
def copiar_semana_anterior(trabajador_id: int, semana_inicio: date, db: Session = Depends(get_db), u: Usuario = Depends(require_role("jefe"))):
    trabajador = db.query(Trabajador).get(trabajador_id)
    if not trabajador:
        raise HTTPException(404, "Trabajador no encontrado")
    
    if u.rol == "jefe" and trabajador.unidad_id != u.unidad_id:
        raise HTTPException(403, "Solo puede programar trabajadores de su unidad")
    
    semana_anterior = semana_inicio - timedelta(days=7)
    
    plan_anterior = db.query(HorarioPlan).filter(
        and_(
            HorarioPlan.trabajador_id == trabajador_id,
            HorarioPlan.semana_inicio == semana_anterior
        )
    ).order_by(HorarioPlan.version.desc()).first()
    
    if not plan_anterior:
        raise HTTPException(404, "No hay horario en la semana anterior para copiar")
    
    plan_in = HorarioPlanIn(
        trabajador_id=trabajador_id,
        semana_inicio=semana_inicio,
        lunes_plantilla_id=plan_anterior.lunes_plantilla_id,
        martes_plantilla_id=plan_anterior.martes_plantilla_id,
        miercoles_plantilla_id=plan_anterior.miercoles_plantilla_id,
        jueves_plantilla_id=plan_anterior.jueves_plantilla_id,
        viernes_plantilla_id=plan_anterior.viernes_plantilla_id,
        sabado_plantilla_id=plan_anterior.sabado_plantilla_id,
        domingo_plantilla_id=plan_anterior.domingo_plantilla_id
    )
    
    return crear_horario(plan_in, db, u)
