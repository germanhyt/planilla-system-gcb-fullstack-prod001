# Interfaz de exportación a Planilla Core — layout `PC-ASIS-1.0`

Endpoint: `POST /reportes/export-planilla-core?empresa_id={id}&periodo=YYYY-MM&formato=csv|json[&solo_cerrado=true]`
(roles RRHH/admin; botón **Exportar a Planilla Core** en la pantalla *Reportes*).

## Reglas
- **Periodo** = mes calendario `YYYY-MM`; cada día se asigna por su **día operativo** (un turno que inicia el 30/31 a las 22:00 y termina al día siguiente pertenece al mes en que inició).
- **Estado**: `FINAL` si el periodo de la empresa está cerrado (`cierre_periodo.estado = cerrado`); si no, el archivo se genera marcado `PRELIMINAR`. Con `solo_cerrado=true` un periodo abierto responde **409** y no se genera nada.
- **Versión**: cada exportación de la misma empresa+periodo incrementa `version_archivo` (v1, v2, ...). Se cuenta sobre la auditoría.
- **Auditoría**: cada exportación crea un registro `auditoria` con `accion=exportar`, `entidad=export_planilla_core`, `entidad_id=EMPRESA:YYYY-MM` y en `despues` los metadatos (layout, estado, versión, archivo, nº trabajadores y líneas). Las descargas CSV/XLSX del consolidado quedan como `entidad=reporte_consolidado`.
- **Nombre de archivo**: `PC_{EMPRESA}_{YYYYMM}_v{N}_{FINAL|PRELIMINAR}.{csv|json}` (también en las cabeceras `X-Export-Estado` y `X-Export-Version`).
- Sólo se emiten líneas con cantidad distinta de 0.

## Catálogo de conceptos
| Código | Descripción | Unidad | Tipo |
|---|---|---|---|
| HN | Horas normales trabajadas (trabajadas − HE) | HORAS | INFORMATIVO |
| TAR | Tardanza | MINUTOS | DESCUENTO |
| HE25 | Horas extra 25% | HORAS | REMUNERATIVO |
| HE35 | Horas extra 35% | HORAS | REMUNERATIVO |
| HNOC | Horas nocturnas 22:00–06:00 (siempre se calculan) | HORAS | INFORMATIVO |
| RNOC | Recargo nocturno — **sólo** empresas con `nocturno.mostrar_sobretasa_separada` (CAVAS sí, GCB SA no) | HORAS | REMUNERATIVO |
| B3AM | Bono nocturno 3 AM: cantidad aprobada; el **monto** lo define administración en Planilla Core | CANTIDAD | INGRESO_INTERNO |
| BHSAL | Saldo del banco de horas al último día del mes | HORAS | INFORMATIVO |

## CSV (UTF-8 sin BOM, separador `;`, punto decimal, una línea por trabajador × concepto)
```
layout_version;empresa_codigo;empresa_ruc;periodo;estado;version_archivo;trabajador_codigo;doc_tipo;doc_numero;concepto_codigo;concepto_tipo;unidad;cantidad
PC-ASIS-1.0;CAVAS;20123456789;2026-10;PRELIMINAR;1;CAV-007;DNI;40000007;HE25;REMUNERATIVO;HORAS;3.0
PC-ASIS-1.0;CAVAS;20123456789;2026-10;PRELIMINAR;1;CAV-007;DNI;40000007;RNOC;REMUNERATIVO;HORAS;14.0
PC-ASIS-1.0;CAVAS;20123456789;2026-10;PRELIMINAR;1;CAV-007;DNI;40000007;B3AM;INGRESO_INTERNO;CANTIDAD;2
```

## JSON
```json
{
  "layout_version": "PC-ASIS-1.0", "empresa_codigo": "CAVAS", "empresa_ruc": "20123456789",
  "periodo": "2026-10", "estado": "FINAL", "version_archivo": 2, "generado_en": "2026-11-01T14:00:00+00:00",
  "conceptos": {"HE25": {"descripcion": "Horas extra 25%", "unidad": "HORAS", "tipo": "REMUNERATIVO"}},
  "lineas": [{"trabajador_codigo": "CAV-007", "doc_tipo": "DNI", "doc_numero": "40000007",
              "trabajador_nombre": "…", "concepto_codigo": "HE25", "concepto_tipo": "REMUNERATIVO",
              "unidad": "HORAS", "cantidad": 3.0}]
}
```
`generado_en` está en UTC. Cambios incompatibles del layout incrementan `layout_version` (p. ej. `PC-ASIS-2.0`).