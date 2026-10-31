"""Worker RQ (cola 'recalc'). Sprint 2: motor de cálculo de asistencia."""
from redis import Redis
from rq import Queue, Worker

from app.config import settings
from app.db import SessionLocal
from app.engine import recalcular_trabajador_periodo
from app.trabajos import ejecutar  # noqa: F401  (S7: jobs encolados como "app.trabajos.ejecutar")


def job_recalcular(trabajador_id: int, periodo: str):
    """Job para RQ: recalcula asistencia de un trabajador en un periodo."""
    db = SessionLocal()
    try:
        recalcular_trabajador_periodo(db, trabajador_id, periodo)
    finally:
        db.close()


def programador(intervalo: int = 60):
    """S7: hilo del worker que dispara la evaluacion diaria de alertas (>= settings.alertas_hora, hora Lima).
    Revisa cada minuto; evaluar_diario() garantiza una sola corrida por dia aunque haya varios workers."""
    import logging
    import time

    from app.alertas import evaluar_diario
    log = logging.getLogger("alertas")
    while True:
        db = SessionLocal()
        try:
            r = evaluar_diario(db)
            if r is not None:
                log.warning("alertas diarias evaluadas: %s", r)
        except Exception:  # noqa: BLE001  el programador no debe tumbar el worker
            log.exception("evaluacion diaria de alertas fallo")
            db.rollback()
        finally:
            db.close()
        time.sleep(intervalo)


if __name__ == "__main__":
    if settings.alertas_diarias:
        import threading
        threading.Thread(target=programador, daemon=True, name="alertas-diarias").start()
    conn = Redis.from_url(settings.redis_url)
    Worker([Queue("recalc", connection=conn)], connection=conn).work()
