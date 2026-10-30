#!/bin/sh
# Arranque del api: migra y, en dev (AUTO_SEED=1), carga la semilla ficticia si la base está vacía.
set -e
alembic upgrade head
if [ "${AUTO_SEED:-0}" = "1" ]; then
  python seed.py --if-empty
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*" --root-path "${ROOT_PATH:-}"
