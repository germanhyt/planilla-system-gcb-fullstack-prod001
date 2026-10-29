"""Worker RQ (cola 'recalc'). En Sprint 1 solo arranca; el motor de cálculo llega en Sprint 2."""
from redis import Redis
from rq import Queue, Worker

from app.config import settings

if __name__ == "__main__":
    conn = Redis.from_url(settings.redis_url)
    Worker([Queue("recalc", connection=conn)], connection=conn).work()
