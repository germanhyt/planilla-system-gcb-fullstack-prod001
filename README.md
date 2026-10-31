# Sistema de Planillas GCB — Sprint 2

Grupo Cordillera Blanca (Perú, `America/Lima`). Base técnica tomada del spike `spike-tareo`:
FastAPI + PostgreSQL 16 + Redis/RQ (worker) + React/TS/Vite PWA servido por nginx, con Docker Compose.

## Sprint 3 — Vistas de marcas (incremento 0+1)
- **Auto-seed en dev**: `backend/start.sh` migra y, con `AUTO_SEED=1` (activado en `docker-compose.dev.yml` y `docker-compose.box.yml`),
  ejecuta `python seed.py --if-empty` (no hace nada si ya hay usuarios). Prod no lo activa.
- **API**: `GET /marcas/mias?desde=YYYY-MM-DD&hasta=YYYY-MM-DD` (trabajador vinculado) y
  `GET /marcas/?desde&hasta&trabajador_id&unidad_id` (jefe: solo su unidad; rrhh/admin: todo). Rango por **día operativo**
  (default últimos 7 días, máx. 93). Cada marca trae `hora_lima`/`ts_lima` (hora servidor en America/Lima), `tipo`, `origen` (gps/qr/manual),
  `geocerca` (dentro/fuera/sin_gps), `distancia_m`, `dia_operativo` y `corte` (CAVAS 06:00) según el rule_set vigente.
- **Web**: "Mis marcas" (trabajador) y "Marcas" (jefe/RRHH/admin) con filtros de fecha, unidad y trabajador.

## Alcance Sprint 2 (Tareo y Asistencia)

**Construido sobre Sprint 1** (PR #1). Implementa el sistema completo de programación de turnos, marcado de asistencia con validación GPS/QR, motor de cálculo diario en RQ worker, y bandeja de regularización para jefes.

### Nuevas Funcionalidades

#### 1. Plantillas de Turno Completas
- **Turnos que cruzan medianoche** (ej. 19:00–02:00): el cálculo respeta el día operativo según corte CAVAS 06:00
- **Refrigerio/break configurable** por plantilla (descontado de horas trabajadas)
- **Turnos rotativos 24/7** (ej. Parking Explanada GCB SA: 3 turnos, 8 personas)

#### 2. Horario Semanal Versionado por Trabajador
- **Versiones**: cada cambio de horario = nueva versión para la misma semana
- **Día a día**: lunes–domingo, cada día con su plantilla de turno (puede ser `null` = descanso)
- **Alertas no bloqueantes**:
  - ⚠️ Jornada >8h/día
  - ⚠️ Total semanal >48h
  - ⚠️ Sin descanso semanal de 24h
  - ⚠️ Part time: promedio diario semanal >4h
- **Copiar semana anterior**: endpoint para duplicar programación con un clic
- **Cálculo por versión vigente**: cada marca usa el plan que estaba vigente ese día

#### 3. Check-in/out desde PWA
- **GPS con geocerca server-side**:
  - Validación de distancia contra `sede.radio_geocerca_m`
  - Estados: `ok` / `fuera_geocerca` (no bloquea, alerta al supervisor)
  - Cálculo haversine en backend
- **QR scanning**:
  - BarcodeDetector API (Chrome/Edge)
  - **Fallback zxing-js/browser para iOS Safari** (sin BarcodeDetector)
  - Campo `qr_code` almacenado en marca
- **Server time autoritativo**: `ts_servidor` es la fuente de verdad
- **Rechazo de duplicados**: ventana de 5 min para evitar marcas duplicadas del mismo tipo
- **Marca manual por jefe/rrhh** con razón auditada

#### 4. Motor de Cálculo Diario (RQ Worker)
- **Job async** `recalcular_trabajador_periodo(trabajador_id, periodo)`
- **Día operativo**:
  - CAVAS: corte 06:00 → marcas antes de 06:00 pertenecen al día anterior
  - GCB SA: día calendario (00:00–24:00)
- **Tardanza** según modo de tolerancia:
  - `umbral_perdona`: si ≤ umbral → 0, si no cuenta todo
  - `umbral_descuenta_exceso`: solo descuenta el exceso sobre el umbral
  - `sin_tolerancia`: cuenta desde el primer minuto
- **Horas trabajadas netas**: entrada–salida menos refrigerio
- **Horas extra solo si pre-programadas**:
  - Split: 25% primeras 2h, 35% resto
  - Exceso no programado → bandeja del jefe para regularización
- **Horas nocturnas 22:00–06:00**: siempre calculadas
- **Periodo operativo**: mes calendario por día operativo (marca 03:00 del 1° → mes anterior si corte = 06:00)
- **Lock de recálculo**: `periodo_cerrado=true` bloquea cambios

#### 5. Bandeja de Regularización (Jefe)
- **Exceso no programado** aparece como `RegularizacionHE` en estado `pendiente`
- **Decisión del jefe**:
  - Aprobar → destino `pago` / `compensacion` / `mixto` (actualiza `asistencia.horas_extra_25/35`)
  - Rechazar → registro auditado, exceso no se paga
- **Filtrado por unidad**: jefe solo ve trabajadores de su unidad
- **Historial completo** por trabajador

#### 6. Tests Completos
- **Motor (`test_engine.py`)**:
  - ✅ Distancia haversine
  - ✅ Día operativo con corte 06:00
  - ✅ Periodo operativo (día 1 a las 03:00 → mes anterior)
  - ✅ Tardanza (3 modos: umbral_perdona, umbral_descuenta_exceso, sin_tolerancia)
  - ✅ Horas nocturnas 22:00–06:00
  - ✅ Horas trabajadas con refrigerio
  - ✅ Split HE 25% / 35%
  - ✅ Turno cruza medianoche
  - ✅ Cálculo completo de asistencia
- **API Marcas (`test_marcas.py`)**:
  - ✅ Registro con GPS
  - ✅ Validación geocerca (ok / fuera)
  - ✅ Rechazo de duplicados
  - ✅ Marca manual por jefe con razón
- **API Horarios (`test_horarios.py`)**:
  - ✅ Creación de plan semanal
  - ✅ Alertas no bloqueantes (>8h/día, >48h/semana, sin descanso)
  - ✅ Copiar semana anterior
- **API Regularizaciones (`test_regularizaciones.py`)**:
  - ✅ Listar pendientes por unidad
  - ✅ Aprobar con destino pago/compensacion/mixto
  - ✅ Rechazar con observación

## Alcance Sprint 1
- **Plataforma**: esquema solo por **Alembic** (`backend/alembic/versions`, sin `create_all`), BD de pruebas aislada
  (`<db>_test`, se recrea y migra en cada corrida de pytest), CI en `.github/workflows/ci.yml` (ruff, pytest con Postgres, build frontend).
- **Auth**: email + contraseña (hash **argon2**), JWT HS256, perfil por usuario (`/me`, `/me/password`, `/me/trabajador`),
  roles `trabajador` / `jefe` / `rrhh` / `admin` con RBAC; el jefe solo ve trabajadores de su unidad.
- **Auditoría** (`auditoria`): todo crear/actualizar/eliminar (con `antes`/`despues`, sin hash de contraseña) + `login_ok`/`login_fallido` con IP.
- **Maestros** (CRUD API + pantallas): empresas, unidades, sedes (lat/lng + radio de geocerca), tipos de contrato configurables
  (FT 208 h/mes 8 h/día, PT85 85 h/mes, PT102 102 h/mes, jornada diaria y refrigerio), trabajadores (jornada diaria override), plantillas de turno.
  Borrado = desactivación lógica.
- **rule_set** versionado por empresa y `valid_from` (inmutable: cambiar = nueva versión). Se guardan overrides y se resuelven sobre la
  lógica BASE (`app/rules.py`) con validación estricta. Reglas confirmadas:
  | Regla | Configuración |
  |---|---|
  | Tolerancia de tardanza | `tolerancia.modo` ∈ `umbral_perdona` / `umbral_descuenta_exceso` / `sin_tolerancia`, `minutos` |
  | CAVAS día operativo | `operativo` 08:00–03:00, `corte` 06:00 (marcas antes de 06:00 → día anterior) |
  | GCB SA | día calendario 24 h, `turno_cuenta_dia_inicio`, hereda la lógica base |
  | Periodo | mes calendario por día operativo |
  | Horas extra | solo pre-programadas; destino `pago`/`compensacion`/`mixto` con default por empresa (CAVAS pago, GCB SA compensación — **supuesto a confirmar**); exceso no programado → bandeja del jefe con regularización auditada |
  | Sobretasa HE | 25 % primeras 2 h, 35 % siguientes |
  | Part time | alerta **no bloqueante** si el promedio diario semanal > 4 h |
  | Nocturnas | 22:00–06:00 siempre calculadas; flag por empresa para mostrar sobretasa nocturna separada (CAVAS sí, GCB SA no — supuesto) |
  | Bono nocturno 3 AM | concepto interno: admin registra por trabajador/periodo, rrhh/otro admin aprueba (no auto-aprobación), historial (`/bonos-nocturnos`) |

## Datos semilla (ficticios)
`backend/seed.py` es idempotente. **Sin nombres, DNI ni sueldos reales** (no existe campo de sueldo; documentos `FICT X0000001…`;
nombres de una lista genérica + apellidos "Ficticio/Demo/…"). El Excel de referencia **no** se copia al repo (`*.xlsx` en `.gitignore`);
se analizó fuera del repo y solo se extrajeron agregados:
- **Dotación Cavas**: ~29–32 personas por mes; mezcla observada en octubre ≈ 6 FT / 26 PT → semilla 32 (6 FT, 13 PT85, 13 PT102; el reparto PT85/PT102 es supuesto 50/50).
- **Contratos**: FT 208 h, PT85 85 h, PT102 102 h/mes (hoja `Consideraciones`); refrigerio PT 45 min.
- **Patrones de turno** (≈2 360 turnos): inicios más frecuentes 19:00, 18:00, 17:00, 11:00, 20:00, 11:30, 16:00;
  fines 02:00, 00:00, 22:00, 01:00, 03:00; duración modal 7 h; ~62 % cruzan medianoche; cierres a las 03:00 (base del bono 3 AM) → 9 plantillas Cavas.
- **Nocturnas** desde las 22:00.
- **No derivado** (el Excel no los trae): áreas/cargos (Salón, Bar, Cocina, Caja, Seguridad, Administración), coordenadas de sedes
  (ficticias, zona Huaraz), unidades GCB SA (Refugio, Parking Explanada 24/7 con 3 turnos rotativos y 8 personas).

Usuarios demo (contraseña `SEED_PASSWORD`, por defecto `Cambiar123!`): `admin@`, `rrhh@`, `jefe@` (Cavas Sisa), `jefe.parking@`, `trabajador@demo.gcb.pe` (vinculado a CAV-007).

## Ejecutar
En este box (dockerd sin iptables → red host; puertos db 5433, redis 6380, api 8001, web 8081):
```bash
cd /workspace/planilla-sprint1
C="sudo docker compose -p planilla-sprint1 -f docker-compose.yml -f docker-compose.box.yml"
$C up -d --build                 # la API ejecuta 'alembic upgrade head' al arrancar
$C exec api python seed.py
$C exec api ruff check .
$C exec api pytest -v            # usa planilla_test (aislada)
# UI: http://localhost:8081  ·  API: http://localhost:8081/api/docs (o :8001/docs)
```
Dev normal (bridge): `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build` (api :8000, web :8080).
Prod (futuro): `docker-compose.prod.yml` une `web` a la red de nginx_proxy con `VIRTUAL_HOST`/`LETSENCRYPT_HOST`; el compose base no publica puertos.
Nueva migración: `$C run --rm -v $PWD/backend:/app api alembic revision --autogenerate -m "..."`.
