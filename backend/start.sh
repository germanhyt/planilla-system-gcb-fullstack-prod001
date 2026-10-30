#!/bin/sh
# Arranque del api: migra y, en dev (AUTO_SEED=1), carga la semilla ficticia si la base está vacía.
set -e
alembic upgrade head
# Prod: SEED_CONFIG=1 carga solo configuración (tipos de contrato, empresas, reglas); nunca datos demo.
if [ "${SEED_CONFIG:-0}" = "1" ]; then
  python seed.py --config-only
fi
if [ "${AUTO_SEED:-0}" = "1" ]; then
  python seed.py --if-empty
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*" --root-path "${ROOT_PATH:-}"
