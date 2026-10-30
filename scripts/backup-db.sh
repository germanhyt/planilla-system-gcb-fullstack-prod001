#!/bin/sh
# Backup de Postgres del stack (pg_dump formato custom, comprimido) con rotación.
# Uso (raíz del repo):  sh scripts/backup-db.sh            # usa docker-compose.yml + prod
#                       COMPOSE_FILES="-f docker-compose.yml -f docker-compose.dev.yml" sh scripts/backup-db.sh
# Cron sugerido (02:30 Lima):  30 2 * * * cd /opt/planilla && sh scripts/backup-db.sh >> backups/backup.log 2>&1
# Restaurar:  docker compose ... exec -T db pg_restore -U planilla -d planilla --clean --if-exists < backups/planilla_X.dump
set -eu
[ -f .env ] && . ./.env
COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP="${BACKUP_KEEP_DAYS:-14}"
mkdir -p "$BACKUP_DIR"
STAMP=$(TZ=America/Lima date +%Y%m%d_%H%M%S)
OUT="$BACKUP_DIR/planilla_${STAMP}.dump"
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES exec -T db pg_dump -U planilla -d planilla -Fc > "$OUT.tmp"
[ -s "$OUT.tmp" ] || { echo "ERROR: backup vacío" >&2; rm -f "$OUT.tmp"; exit 1; }
mv "$OUT.tmp" "$OUT"
# Verificación: el dump debe poder listarse
# shellcheck disable=SC2086
docker compose $COMPOSE_FILES exec -T db pg_restore -l < "$OUT" > /dev/null
find "$BACKUP_DIR" -name 'planilla_*.dump' -mtime +"$KEEP" -delete
echo "OK $OUT ($(du -h "$OUT" | cut -f1))"
