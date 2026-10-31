"""Sprint 7: trabajos en segundo plano (RQ, cola 'recalc') con estado/progreso en la tabla `trabajo`.

- Pequenos (<= settings.jobs_umbral_sync trabajadores) se ejecutan en la misma peticion.
- Grandes se encolan en RQ; si Redis no responde (o JOBS_MODO=inline, p. ej. tests) se ejecutan en linea.
"""
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .models import Trabajo

COLA = "recalc"


def crear(db: Session, tipo: str, parametros: dict, user_id: Optional[int], empresa_id: Optional[int] = None,
          total: int = 0) -> Trabajo:
    t = Trabajo(tipo=tipo, estado="pendiente", parametros=parametros, creado_por=user_id, empresa_id=empresa_id,
                total=total, progreso=0)
    db.add(t)
    db.commit()
    return t


def _cola():
    from redis import Redis
    from rq import Queue
    conn = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
    conn.ping()
    return Queue(COLA, connection=conn)


def encolar(trabajo_id: int) -> str:
    """Encola en RQ o ejecuta en linea. Devuelve el modo usado: rq | inline | inline_sin_redis."""
    if settings.jobs_modo == "inline":
        ejecutar(trabajo_id)
        return "inline"
    try:
        _cola().enqueue("app.trabajos.ejecutar", trabajo_id, job_timeout=3600)
        return "rq"
    except Exception:  # noqa: BLE001 - sin Redis no se bloquea la operacion
        ejecutar(trabajo_id)
        return "inline_sin_redis"


def avanzar(db: Session, t: Trabajo, n: int) -> None:
    t.progreso = n
    db.commit()


def _recalcular(db: Session, t: Trabajo) -> dict:
    from .alertas import generar
    from .engine import recalcular_trabajador_periodo
    p = t.parametros
    tids = p["trabajadores"]
    t.total = len(tids)
    hechos = 0
    for i, tid in enumerate(tids, 1):
        hechos += bool(recalcular_trabajador_periodo(db, tid, p["periodo"]))
        if i % 5 == 0 or i == len(tids):
            avanzar(db, t, i)
    generar(db, p["empresa_id"], p["periodo"])
    return {"periodo": p["periodo"], "trabajadores_recalculados": hechos}


def _export_lote(db: Session, t: Trabajo) -> dict:
    from .export_pc import generar_export
    from .models import Empresa
    p = t.parametros
    t.total = len(p["empresas"])
    archivos = []
    for i, eid in enumerate(p["empresas"], 1):
        row, reutilizada = generar_export(db, db.get(Empresa, eid), p["periodo"], p["formato"], t.creado_por)
        archivos.append({"empresa_id": eid, "export_id": row.id, "archivo": row.archivo, "version": row.version,
                         "estado": row.estado, "checksum": row.checksum, "reutilizada": reutilizada})
        avanzar(db, t, i)
    return {"periodo": p["periodo"], "archivos": archivos}


HANDLERS: dict[str, Callable[[Session, Trabajo], dict]] = {"recalcular": _recalcular, "export_lote": _export_lote}


def ejecutar(trabajo_id: int) -> None:
    """Punto de entrada del worker RQ (y del modo en linea). Usa su propia sesion."""
    from .audit import audit
    db = SessionLocal()
    try:
        t = db.get(Trabajo, trabajo_id)
        if t is None or t.estado in ("ok", "error"):
            return
        t.estado = "en_curso"
        db.commit()
        try:
            t.resultado = HANDLERS[t.tipo](db, t)
            t.estado, t.progreso = "ok", t.total
            audit(db, t.creado_por, t.tipo, "trabajo", t.id, None, {"parametros": t.parametros} | (t.resultado or {}))
        except Exception as e:  # noqa: BLE001
            db.rollback()
            t = db.get(Trabajo, trabajo_id)
            t.estado, t.error = "error", str(e)[:2000]
        t.terminado_en = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def out(t: Trabajo) -> dict:
    pct = 100 if t.estado == "ok" else (int(t.progreso * 100 / t.total) if t.total else 0)
    return {"id": t.id, "tipo": t.tipo, "estado": t.estado, "progreso": t.progreso, "total": t.total,
            "porcentaje": pct, "empresa_id": t.empresa_id, "parametros": t.parametros, "resultado": t.resultado,
            "error": t.error, "creado_en": t.creado_en.isoformat() if t.creado_en else None,
            "terminado_en": t.terminado_en.isoformat() if t.terminado_en else None}
