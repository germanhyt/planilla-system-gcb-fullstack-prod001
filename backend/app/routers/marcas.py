"""API de marcas (check-in/out) con validación GPS/QR. Sprint 2."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..audit import audit
from ..db import get_db
from ..deps import require
from ..engine import calcular_distancia
from ..models import Marca, Sede, Trabajador, Usuario
from ..schemas import MarcaIn, MarcaManualIn

r = APIRouter(prefix="/marcas", tags=["marcas"])


def validar_geocerca(db: Session, trabajador_id: int, lat: float, lng: float) -> tuple[str, float, int]:
    """Valida que la marca esté dentro de la geocerca de la sede del trabajador."""
    trabajador = db.query(Trabajador).get(trabajador_id)
    if not trabajador or not trabajador.sede_id:
        return "ok", 0.0, None
    
    sede = db.query(Sede).get(trabajador.sede_id)
    if not sede:
        return "ok", 0.0, None
    
    distancia = calcular_distancia(float(sede.lat), float(sede.lng), lat, lng)
    
    if distancia > sede.radio_geocerca_m:
        return "fuera_geocerca", distancia, sede.id
    
    return "ok", distancia, sede.id


def verificar_duplicado(db: Session, trabajador_id: int, tipo: str, ventana_min: int = 5) -> bool:
    """Verifica si ya existe una marca del mismo tipo en los últimos N minutos."""
    ahora = datetime.now(timezone.utc)
    hace_n_min = ahora - timedelta(minutes=ventana_min)
    
    existe = db.query(Marca).filter(
        and_(
            Marca.trabajador_id == trabajador_id,
            Marca.tipo == tipo,
            Marca.ts_servidor >= hace_n_min
        )
    ).first()
    
    return existe is not None


@r.post("/")
def registrar_marca(marca_in: MarcaIn, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(require("trabajador", "jefe", "rrhh", "admin"))):
    trabajador = db.query(Trabajador).filter(Trabajador.usuario_id == u.id).first()
    if not trabajador:
        raise HTTPException(403, "Usuario no vinculado a trabajador")
    
    if verificar_duplicado(db, trabajador.id, marca_in.tipo):
        raise HTTPException(400, "Ya existe una marca del mismo tipo en los últimos 5 minutos")
    
    validacion_estado = "ok"
    distancia_m = None
    sede_id = None
    
    if marca_in.lat is not None and marca_in.lng is not None:
        validacion_estado, distancia_m, sede_id = validar_geocerca(db, trabajador.id, marca_in.lat, marca_in.lng)
    
    ts_servidor = datetime.now(timezone.utc)
    
    marca = Marca(
        trabajador_id=trabajador.id,
        tipo=marca_in.tipo,
        ts_servidor=ts_servidor,
        ts_cliente=marca_in.ts_cliente,
        lat=marca_in.lat,
        lng=marca_in.lng,
        distancia_m=distancia_m,
        sede_id=sede_id,
        metodo="gps",
        qr_code=marca_in.qr_code,
        validacion_estado=validacion_estado
    )
    
    db.add(marca)
    db.commit()
    db.refresh(marca)
    
    ip = request.client.host if request.client else None
    audit(db, u.id, "crear", "marca", str(marca.id), None, {
        "trabajador_id": trabajador.id,
        "tipo": marca_in.tipo,
        "validacion": validacion_estado
    }, ip)
    
    return {
        "id": marca.id,
        "ts_servidor": ts_servidor.isoformat(),
        "validacion_estado": validacion_estado,
        "distancia_m": distancia_m
    }


@r.post("/manual")
def registrar_marca_manual(
    marca_in: MarcaManualIn,
    request: Request,
    db: Session = Depends(get_db),
    u: Usuario = Depends(require("jefe", "rrhh", "admin"))
):
    trabajador = db.query(Trabajador).get(marca_in.trabajador_id)
    if not trabajador:
        raise HTTPException(404, "Trabajador no encontrado")
    
    if u.rol == "jefe" and trabajador.unidad_id != u.unidad_id:
        raise HTTPException(403, "Solo puede marcar trabajadores de su unidad")
    
    marca = Marca(
        trabajador_id=marca_in.trabajador_id,
        tipo=marca_in.tipo,
        ts_servidor=marca_in.ts_servidor,
        sede_id=marca_in.sede_id,
        metodo="manual",
        razon_manual=marca_in.razon_manual,
        registrado_por=u.id,
        validacion_estado="ok"
    )
    
    db.add(marca)
    db.commit()
    db.refresh(marca)
    
    ip = request.client.host if request.client else None
    audit(db, u.id, "crear", "marca", str(marca.id), None, {
        "trabajador_id": marca_in.trabajador_id,
        "tipo": marca_in.tipo,
        "metodo": "manual",
        "razon": marca_in.razon_manual
    }, ip)
    
    return {"id": marca.id, "ts_servidor": marca.ts_servidor.isoformat()}


@r.get("/trabajador/{trabajador_id}")
def listar_marcas(
    trabajador_id: int,
    fecha_inicio: str = None,
    fecha_fin: str = None,
    db: Session = Depends(get_db),
    u: Usuario = Depends(require("trabajador", "jefe", "rrhh", "admin"))
):
    trabajador = db.query(Trabajador).get(trabajador_id)
    if not trabajador:
        raise HTTPException(404, "Trabajador no encontrado")
    
    if u.rol == "trabajador":
        mi_trabajador = db.query(Trabajador).filter(Trabajador.usuario_id == u.id).first()
        if not mi_trabajador or mi_trabajador.id != trabajador_id:
            raise HTTPException(403, "Solo puede ver sus propias marcas")
    
    if u.rol == "jefe" and trabajador.unidad_id != u.unidad_id:
        raise HTTPException(403, "Solo puede ver trabajadores de su unidad")
    
    query = db.query(Marca).filter(Marca.trabajador_id == trabajador_id)
    
    if fecha_inicio:
        query = query.filter(Marca.ts_servidor >= datetime.fromisoformat(fecha_inicio))
    
    if fecha_fin:
        query = query.filter(Marca.ts_servidor < datetime.fromisoformat(fecha_fin))
    
    marcas = query.order_by(Marca.ts_servidor.desc()).limit(100).all()
    
    return [{
        "id": m.id,
        "tipo": m.tipo,
        "ts_servidor": m.ts_servidor.isoformat(),
        "ts_cliente": m.ts_cliente.isoformat() if m.ts_cliente else None,
        "metodo": m.metodo,
        "validacion_estado": m.validacion_estado,
        "distancia_m": float(m.distancia_m) if m.distancia_m else None,
        "razon_manual": m.razon_manual
    } for m in marcas]
