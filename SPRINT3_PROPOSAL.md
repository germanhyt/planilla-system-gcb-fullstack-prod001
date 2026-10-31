# Sprint 3: Propuesta de Reportes, Dashboard y Cierre Contable

**Sistema de Planillas GCB — Grupo Cordillera Blanca (Perú, `America/Lima`)**

Construido sobre Sprint 2 (tareo y asistencia). Sprint 3 cierra el ciclo de nómina con reportes ejecutivos, dashboard de excepciones, y cierre contable para integración con sistemas externos.

---

## Alcance Propuesto Sprint 3

### 1. Reportes y Export

#### Reporte Consolidado Mensual por Trabajador
- **Vista**: Tabla resumen con todas las asistencias del mes
- **Columnas**: Día, entrada, salida, horas trabajadas, HE 25%, HE 35%, nocturnas, tardanza (min)
- **Filtros**: Periodo, empresa, unidad, trabajador
- **Totales**: Suma de horas ordinarias, HE, nocturnas, tardanzas del mes
- **Export Excel**: Generación server-side con openpyxl o xlsxwriter
  - Formato predefinido para integración con sistema de nómina externo
  - Incluye conceptos remunerativos: HE 25%, HE 35%, nocturnas, descuento tardanzas
  - Sheet separada con resumen ejecutivo

#### Resumen Ejecutivo (Dashboard Gerencial)
- **KPIs por empresa/unidad**:
  - Total trabajadores activos
  - Asistencia promedio (%)
  - Tardanzas acumuladas (horas)
  - HE acumuladas (horas y % vs programadas)
  - Faltas sin justificación
- **Gráficos**:
  - Serie de tiempo: asistencia diaria del mes
  - Distribución de HE por tipo (pago/compensación)
  - Top 10 tardanzas por trabajador
- **Alertas agregadas**:
  - Trabajadores con >3 tardanzas en el mes
  - Exceso de HE vs presupuesto (alerta si >10% del plan)
  - Incumplimientos de descanso semanal

#### Export API para Integración
- **Endpoint REST**: `/reportes/conceptos-remunerativos`
  - Parámetros: `periodo`, `empresa_id`
  - Formato JSON estructurado:
    ```json
    {
      "periodo": "2026-10",
      "empresa": "CAVAS",
      "trabajadores": [
        {
          "codigo": "CAV-001",
          "conceptos": {
            "horas_ordinarias": 160.5,
            "he_25": 4.0,
            "he_35": 2.5,
            "nocturnas": 12.0,
            "tardanzas_min": 15
          }
        }
      ]
    }
    ```
- **Autenticación**: JWT con rol `rrhh` o `admin` + API key opcional para sistemas externos

### 2. Bandeja de Excepciones (Jefe/RRHH)

#### Vista Unificada de Excepciones
- **Faltas sin justificación**: Días sin marca (entrada o salida) con horario programado
- **Tardanzas recurrentes**: Alerta automática si trabajador tiene >3 tardanzas en el mes
- **Varianza horas trabajadas vs programadas**: Alerta si diferencia >20% en la semana
- **Exceso de HE no regularizado**: Contador de regularizaciones pendientes >7 días

#### Acciones desde Bandeja
- **Justificar falta**: Jefe/RRHH registra motivo (permiso, licencia médica, vacaciones)
  - Auditoría completa con adjuntos (PDF escaneado opcional)
- **Marcar como "revisado"**: Para excepciones que no requieren acción
- **Enviar notificación al trabajador**: Email o push notification con solicitud de justificación

#### Filtros y Búsqueda
- Por empresa, unidad, trabajador
- Por tipo de excepción (falta, tardanza, exceso HE)
- Por estado (pendiente, revisado, justificado)
- Rango de fechas

### 3. Cierre Contable (Lock de Periodo)

#### Cierre de Periodo Mensual
- **Acción**: RRHH/admin ejecuta "Cerrar periodo YYYY-MM"
- **Efecto**:
  - `asistencia.periodo_cerrado = true` para todos los registros del periodo
  - Bloqueo de recálculo: job RQ rechaza `recalcular_trabajador_periodo` si `periodo_cerrado=true`
  - Bloqueo de marcas retroactivas: endpoint `/marcas/manual` valida que el día no esté cerrado
- **Auditoría**: Registro en `auditoria` con acción `cerrar_periodo` y usuario responsable
- **Reapertura excepcional**: Solo admin puede reabrir con razón obligatoria (auditada)

#### Histórico de Cierres
- **Tabla**: `/periodos-cerrados` (nueva tabla `cierre_periodo`)
  - Campos: `periodo`, `empresa_id`, `cerrado_por`, `cerrado_en`, `reabierto_por`, `reabierto_en`, `razon_reapertura`
- **Vista**: Lista de cierres históricos con estado (cerrado/reabierto)

### 4. Notificaciones y Alertas

#### Notificaciones Push (PWA)
- **Trabajador olvida salida**: Push a las 2h después del fin de turno programado
- **Exceso no programado registrado**: Notificación al trabajador y jefe
- **Periodo próximo a cerrar**: Recordatorio a RRHH 3 días antes del cierre

#### Alertas por Email/Slack (Configurable)
- **Jefe**: Resumen diario de excepciones de su unidad
- **RRHH**: Alerta si >10 regularizaciones pendientes
- **Admin**: Alerta de incumplimiento normativo (descanso semanal, PT >4h/día promedio)

#### Configuración de Alertas
- **Tabla**: `notificacion_config` (por usuario/rol)
  - Campos: `usuario_id`, `canal` (email/slack/push), `tipo_alerta`, `habilitado`
- **UI**: Perfil de usuario con checkboxes para activar/desactivar alertas

### 5. Mejoras UX PWA

#### Modo Offline
- **Service Worker**: Cache de marcas para envío diferido cuando vuelva conexión
- **IndexedDB**: Almacenamiento local de horarios de la semana
- **Indicador de sincronización**: Badge que muestra marcas pendientes de enviar

#### Historial de Marcas del Trabajador
- **Vista**: Lista de últimas 30 marcas con:
  - Fecha/hora, tipo (entrada/salida), método (GPS/QR/manual)
  - Validación (ok/fuera_geocerca), distancia
- **Filtros**: Por mes, por tipo

#### Vista de Horario Semanal Asignado
- **Calendario semanal**: Muestra las plantillas de turno asignadas lunes–domingo
- **Alertas visibles**: Warnings de >8h/día o >48h/semana
- **Versión histórica**: Selector para ver versiones anteriores del horario

### 6. Histórico de Versiones de rule_set

#### Vista de Cambios en Reglas
- **Endpoint**: `/rule-sets/historial?empresa_id=X`
- **Retorna**: Lista de todas las versiones del `rule_set` con:
  - `valid_from`, `version`, `creado_por`, `motivo`
  - Diff visual de campos cambiados entre versiones
- **Uso**: Auditoría de cambios normativos y rastreo de cálculos históricos

---

## Entregables Esperados

### Backend
- ✅ `app/routers/reportes.py`: Consolidado mensual, resumen ejecutivo, export Excel
- ✅ `app/routers/excepciones.py`: Bandeja unificada + acciones (justificar, revisar)
- ✅ `app/routers/periodos.py`: Cierre/reapertura de periodo
- ✅ `app/models.py`: Nuevas tablas `cierre_periodo`, `excepcion`, `notificacion_config`, `falta_justificada`
- ✅ `app/notificaciones.py`: Módulo de envío de push/email/Slack
- ✅ Migración Alembic Sprint 3

### Frontend
- ✅ `frontend/src/Reportes.tsx`: Vista de reportes con filtros y export
- ✅ `frontend/src/Dashboard.tsx`: KPIs y gráficos ejecutivos
- ✅ `frontend/src/Excepciones.tsx`: Bandeja de excepciones con acciones
- ✅ `frontend/src/Horario.tsx`: Calendario semanal del trabajador
- ✅ Service Worker actualizado con modo offline
- ✅ IndexedDB para cache de marcas

### Tests
- ✅ `test_reportes.py`: Export Excel, consolidado mensual, conceptos remunerativos
- ✅ `test_excepciones.py`: Listar faltas, tardanzas recurrentes, justificar
- ✅ `test_cierre_periodo.py`: Cerrar/reabrir, bloqueo de recálculo, auditoría
- ✅ `test_notificaciones.py`: Push, email, alertas configurables

---

## Riesgos y Supuestos

### Riesgos
1. **Integración con sistema externo de nómina**: Requiere validación del formato de export con el proveedor actual (si existe).
2. **Notificaciones push**: Requiere configuración de Firebase Cloud Messaging o servicio equivalente.
3. **Slack integration**: Requiere Slack Webhook URL configurado en variables de entorno.

### Supuestos a Confirmar
1. **Formato de export Excel**: ¿El cliente tiene un template predefinido o aceptan el estándar propuesto?
2. **Cierre de periodo**: ¿Fecha de cierre fija (ej. día 5 del mes siguiente) o manual?
3. **Justificación de faltas**: ¿Requiere adjuntos (PDF escaneados) o solo texto?
4. **Alertas Slack**: ¿Canal específico por empresa/unidad o un canal global?

---

## Estimación de Complejidad

**Sprint 3 vs Sprint 2**: Similar en alcance. Sprint 2 implementó el núcleo de cálculo y marcado; Sprint 3 cierra el ciclo con reportería y operaciones administrativas.

**Componentes principales**:
- Reportes y export (Excel): complejidad media (librerías estándar)
- Dashboard con gráficos: complejidad media (librería de charts en frontend)
- Bandeja de excepciones: complejidad baja (CRUD + lógica de alertas)
- Cierre de periodo: complejidad baja (flag booleano + validaciones)
- Notificaciones: complejidad alta (integración con servicios externos)
- Modo offline PWA: complejidad alta (Service Worker + IndexedDB)

**Tests**: ~15–20 tests nuevos (mantener coverage >80%).

---

## Orden de Desarrollo Recomendado

1. **Semana 1**: Reportes y export Excel (core value: integración con nómina)
2. **Semana 2**: Bandeja de excepciones + cierre de periodo (operaciones RRHH)
3. **Semana 3**: Notificaciones (push + email) + dashboard ejecutivo
4. **Semana 4**: Mejoras PWA (offline, historial marcas) + tests completos

---

**Listo para planificación y kick-off Sprint 3.** 🚀
