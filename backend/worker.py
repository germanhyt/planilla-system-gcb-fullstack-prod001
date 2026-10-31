"""Worker RQ (cola 'recalc'). Sprint 2: motor de cálculo de asistencia."""
from redis import Redis
from rq import Queue, Worker

from app.config import settings
from app.db import SessionLocal
from app.engine import recalcular_trabajador_periodo


def job_recalcular(trabajador_id: int, periodo: str):
    """Job para RQ: recalcula asistencia de un trabajador en un periodo."""
    db = SessionLocal()
    try:
        recalcular_trabajador_periodo(db, trabajador_id, periodo)
    finally:
        db.close()


if __name__ == "__main__":
    conn = Redis.from_url(settings.redis_url)
    Worker([Queue("recalc", connection=conn)], connection=conn).work()
