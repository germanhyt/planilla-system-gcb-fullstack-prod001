# Piloto Cavas — guía de despliegue y operación

Estado: **preparado, no desplegado**. Rama `feat/s4-piloto`.

## 1. Alcance del piloto
- Unidad **Cavas** (corte de día operativo 06:00, America/Lima). Usuarios: trabajadores de Cavas, su jefe, RRHH y admin.
- Funcionalidad: marcas GPS/QR (con cola offline), horario asignado con vigencia y rotación, HE programadas por el jefe,
  bandeja de HE no programadas, justificación de faltas (trabajador solicita → jefe decide), bolsa de horas,
  bono 3 AM, reportes/consolidado, cierre y reapertura de periodo.

## 2. Requisitos del servidor
- Docker + Docker Compose v2. Contenedores `nginx-proxy` y `acme-companion` ya corriendo en la red externa `nginx-proxy`
  (o la indicada en `PROXY_NETWORK`).
- Dominio de producción: **`planilla.gcb.pe`** (`WEB_HOST`); certificado Let's Encrypt con **`sistemas@gcb.pe`** (`LETSENCRYPT_EMAIL`).
- DNS: registro A de `planilla.gcb.pe` apuntando al servidor (necesario para Let's Encrypt).

## 3. Despliegue
```sh
git clone ... && cd planilla-system-gcb-fullstack-prod001 && git checkout feat/s4-piloto
cp .env.example .env          # completar DB_PASSWORD, JWT_SECRET (openssl rand -base64 48), WEB_HOST, LETSENCRYPT_EMAIL
docker compose -f docker-compose.yml -f docker-compose.prod.yml config >/dev/null   # valida variables obligatorias
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
curl -fsS https://planilla.gcb.pe/api/health    # {"ok":true}
```
- El api ejecuta `alembic upgrade head` al arrancar. En prod **no** se carga la semilla ficticia (`AUTO_SEED=0`).
- Carga inicial (RRHH/admin desde la web o importación): empresa, unidad Cavas, sedes (con geocerca), tipos de contrato
  (incluido `refrigerio_min`), plantillas de turno, trabajadores, usuarios y rule_set vigente desde el inicio del piloto.
- **Refrigerio**: 45 min para FT y para part-time PT85/PT102 (decisión PO; configurable en `tipo_contrato.refrigerio_min`).
- **Reglas CAVAS reales vigentes desde 2026-11-01** (tolerancia umbral 10 min, corte 06:00, HE por defecto a pago,
  sobretasa nocturna en columna aparte). La vigencia es configurable y versionada: admin publica una nueva versión con
  `POST /rule-sets` (`empresa_id`, `valid_from`, `config`, `motivo`); las versiones son inmutables (sin PUT/DELETE) y
  auditadas; corregir = publicar otra versión con otra fecha. Publicar una versión **no recalcula** periodos (ni cerrados
  ni abiertos); los abiertos la toman en su próximo recálculo. En prod (sin semilla) cargar la versión CAVAS real con
  `valid_from` = fecha de inicio del piloto.
  **Sin rule_set vigente el motor no calcula ese periodo** (el recálculo lo omite sin error).

## 4. Operación diaria
| Rol | Qué hace |
|---|---|
| Trabajador | Marca entrada/salida (GPS/QR). Sin red, la marca queda en cola y se envía sola; si la sesión venció, al volver a ingresar se reenvía. Solicita justificación de faltas. |
| Jefe | Asigna horarios (vigencia/rotación), programa HE, decide HE no programadas y justificaciones de su unidad. |
| RRHH | Revisa excepciones/reportes, bono 3 AM, checklist y cierre de periodo; puede recalcular (`POST /periodos/recalcular`). |
| Admin | Maestros, reglas, reapertura de periodos (con motivo, auditada). |

- Cambiar HE programadas o un horario asignado **dispara el recálculo** de los periodos abiertos afectados (hasta el mes actual).
- El recálculo **conserva** las regularizaciones de HE ya aprobadas/rechazadas; solo regenera las pendientes.
- Periodo cerrado: todo cambio responde 409; reabrir solo admin.

## 5. Backups
- `sh scripts/backup-db.sh` (Linux/prod; cron sugerido 02:30) o `powershell -File scripts/backup-db.ps1 [-Prod]`.
- Formato `pg_dump -Fc`, verificado con `pg_restore -l`, rotación `BACKUP_KEEP_DAYS` (14).
- **PENDIENTE (decisión abierta)**: destino de copia fuera del servidor (`BACKUP_OFFSITE_DEST` en `.env.example`).
  Hasta definirlo, copiar `backups/` manualmente fuera del servidor.
- Restaurar: `docker compose ... exec -T db pg_restore -U planilla -d planilla --clean --if-exists < backups/planilla_X.dump`.
- **Nunca** `docker compose down -v` (borra el volumen `pgdata`).

## 6. Pruebas
- Backend: `pytest` en contenedor contra `planilla_test`. Frontend: `npm test` (vitest), `npm run build`.
- E2E de humo (solo lectura, seguro contra dev): `powershell -File e2e/run-e2e.ps1` (contenedor Playwright → `:8080`).

## 7. Checklist de salida a piloto
- [ ] `.env` con secretos reales (no los por defecto); `.env` fuera de git.
- [ ] DNS + certificado emitido; `/api/health` OK por HTTPS.
- [ ] Maestros y rule_set cargados; plantillas y asignaciones de horario de Cavas.
- [ ] Usuarios creados y contraseñas entregadas; prueba de marca GPS en cada sede (geocerca).
- [ ] Backup diario programado y una restauración de prueba realizada.
- [ ] Decisiones abiertas resueltas (ver informe de sprint 4): destino de backup fuera del servidor, política de recálculo masivo, jornada de capacitación.
- [x] Refrigerio PT = 45 min; reglas CAVAS reales desde 2026-11-01; dominio `planilla.gcb.pe`; correo LE `sistemas@gcb.pe`.
