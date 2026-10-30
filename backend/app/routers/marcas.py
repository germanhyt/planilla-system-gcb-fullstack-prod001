"""API de marcas (check-in/out) con validación GPS/QR. Sprint 2."""
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from ..audit import audit
from ..cierre import exigir_abierto_ts
from ..db import get_db
from ..deps import require
from ..engine import calcular_distancia, get_dia_operativo
from ..models import Marca, RuleSet, Sede, Trabajador, Usuario
from ..rules import efectivas
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
    exigir_abierto_ts(db, trabajador, ts_servidor)

    marca = Marca(
        trabajador_id=trabajador.id,
        tipo=marca_in.tipo,
        ts_servidor=ts_servidor,
        ts_cliente=marca_in.ts_cliente,
        lat=marca_in.lat,
        lng=marca_in.lng,
        distancia_m=distancia_m,
        sede_id=sede_id,
        metodo="qr" if marca_in.qr_code else "gps",
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
    exigir_abierto_ts(db, trabajador, marca_in.ts_servidor)

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


# ---------------------------------------------------------------------------
# Sprint 3: vistas de registros de marcas
# ---------------------------------------------------------------------------
LIMA = ZoneInfo("America/Lima")


def _corte_empresa(db: Session, empresa_id: int, dia: date, cache: dict) -> str:
    """Hora de corte del día operativo según el rule_set vigente (CAVAS 06:00, GCB SA 00:00)."""
    key = (empresa_id, dia)
    if key not in cache:
        rs = db.query(RuleSet).filter(RuleSet.empresa_id == empresa_id, RuleSet.valid_from <= dia) \
            .order_by(RuleSet.valid_from.desc()).first()
        corte = "00:00"
        if rs:
            try:
                corte = efectivas(rs.config or {})["dia_operativo"].get("corte") or "00:00"
            except Exception:  # noqa: BLE001 - config inválida: se asume día calendario
                corte = "00:00"
        cache[key] = corte
    return cache[key]


def _origen(m: Marca) -> str:
    if m.metodo == "manual":
        return "manual"
    return "qr" if (m.metodo == "qr" or m.qr_code) else "gps"


def _geocerca(m: Marca) -> str:
    if m.lat is None or m.lng is None:
        return "sin_gps"
    return "fuera" if m.validacion_estado == "fuera_geocerca" else "dentro"


def _parse_fecha(v: Optional[str], nombre: str) -> Optional[date]:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError as e:
        raise HTTPException(422, f"{nombre} debe tener formato YYYY-MM-DD") from e


def _consultar(db: Session, trabajadores: dict[int, Trabajador], desde: Optional[str], hasta: Optional[str]) -> list[dict]:
    """Marcas de los trabajadores dados, filtradas por día operativo [desde, hasta] (fechas Lima)."""
    hoy = datetime.now(LIMA).date()
    d_hasta = _parse_fecha(hasta, "hasta") or hoy
    d_desde = _parse_fecha(desde, "desde") or (d_hasta - timedelta(days=6))
    if d_desde > d_hasta:
        raise HTTPException(422, "'desde' no puede ser posterior a 'hasta'")
    if (d_hasta - d_desde).days > 92:
        raise HTTPException(422, "El rango máximo es de 93 días")
    if not trabajadores:
        return []
    # ventana amplia en hora Lima: el corte máximo es < 24h, el día operativo 'hasta' termina antes de hasta+2 00:00
    ini = datetime.combine(d_desde, time(0), LIMA)
    fin = datetime.combine(d_hasta + timedelta(days=2), time(0), LIMA)
    marcas = db.query(Marca).filter(Marca.trabajador_id.in_(list(trabajadores)), Marca.ts_servidor >= ini,
                                    Marca.ts_servidor < fin).order_by(Marca.ts_servidor.desc()).all()
    cache: dict = {}
    out = []
    for m in marcas:
        t = trabajadores[m.trabajador_id]
        ts_lima = m.ts_servidor.astimezone(LIMA)
        corte = _corte_empresa(db, t.empresa_id, ts_lima.date(), cache)
        dia_op = get_dia_operativo(ts_lima.replace(tzinfo=None), corte)
        if not (d_desde <= dia_op <= d_hasta):
            continue
        out.append({
            "id": m.id,
            "trabajador_id": t.id,
            "trabajador_codigo": t.codigo,
            "trabajador_nombre": f"{t.nombres} {t.apellidos}",
            "unidad_id": t.unidad_id,
            "tipo": m.tipo,
            "ts_servidor": m.ts_servidor.isoformat(),
            "ts_lima": ts_lima.isoformat(),
            "fecha_lima": ts_lima.date().isoformat(),
            "hora_lima": ts_lima.strftime("%H:%M:%S"),
            "origen": _origen(m),
            "geocerca": _geocerca(m),
            "distancia_m": float(m.distancia_m) if m.distancia_m is not None else None,
            "validacion_estado": m.validacion_estado,
            "dia_operativo": dia_op.isoformat(),
            "corte": corte,
            "razon_manual": m.razon_manual,
        })
    return out


@r.get("/mias")
def mis_marcas(desde: Optional[str] = None, hasta: Optional[str] = None, db: Session = Depends(get_db),
               u: Usuario = Depends(require("trabajador", "jefe", "rrhh", "admin"))):
    """Marcas del trabajador vinculado al usuario, por rango de día operativo (default: últimos 7 días)."""
    t = db.query(Trabajador).filter(Trabajador.usuario_id == u.id).first()
    if not t:
        raise HTTPException(404, "Usuario no vinculado a trabajador")
    return _consultar(db, {t.id: t}, desde, hasta)


@r.get("/")
def marcas_por_trabajador_fecha(desde: Optional[str] = None, hasta: Optional[str] = None,
                                trabajador_id: Optional[int] = None, unidad_id: Optional[int] = None,
                                db: Session = Depends(get_db), u: Usuario = Depends(require("jefe", "rrhh", "admin"))):
    """Marcas por trabajador/fecha. Jefe: solo su unidad. RRHH/admin: todo."""
    if u.rol == "jefe":
        if not u.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        if unidad_id is not None and unidad_id != u.unidad_id:
            raise HTTPException(403, "Solo puede ver trabajadores de su unidad")
        unidad_id = u.unidad_id
    q = db.query(Trabajador)
    if unidad_id is not None:
        q = q.filter(Trabajador.unidad_id == unidad_id)
    if trabajador_id is not None:
        t = db.get(Trabajador, trabajador_id)
        if not t:
            raise HTTPException(404, "Trabajador no encontrado")
        if u.rol == "jefe" and t.unidad_id != u.unidad_id:
            raise HTTPException(403, "Solo puede ver trabajadores de su unidad")
        q = q.filter(Trabajador.id == trabajador_id)
    trabajadores = {t.id: t for t in q.all()}
    return _consultar(db, trabajadores, desde, hasta)
