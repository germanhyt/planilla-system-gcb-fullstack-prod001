# Interfaz de exportación a Planilla Core — layout `PC-ASIS-1.1`

Endpoint: `POST /reportes/export-planilla-core?empresa_id={id}&periodo=YYYY-MM&formato=csv|json[&solo_cerrado=true]`
(roles RRHH/admin; botón **Exportar a Planilla Core** en la pantalla *Reportes*).

## Reglas
- **Periodo** = mes calendario `YYYY-MM`; cada día se asigna por su **día operativo** (un turno que inicia el 30/31 a las 22:00 y termina al día siguiente pertenece al mes en que inició).
- **Estado**: `FINAL` si el periodo de la empresa está cerrado (`cierre_periodo.estado = cerrado`); si no, el archivo se genera marcado `PRELIMINAR`. Con `solo_cerrado=true` un periodo abierto responde **409** y no se genera nada.
- **Versión**: cada exportación de la misma empresa+periodo incrementa `version_archivo` (v1, v2, ...). Desde S7 cada versión se guarda en `export_planilla` con checksum; re-exportar sin cambios reutiliza la última versión (ver [contrato](contratos/PC-ASIS-1.1.md)).
- **Auditoría**: cada exportación crea un registro `auditoria` con `accion=exportar`, `entidad=export_planilla_core`, `entidad_id=EMPRESA:YYYY-MM` y en `despues` los metadatos (layout, estado, versión, archivo, nº trabajadores y líneas). Las descargas CSV/XLSX del consolidado quedan como `entidad=reporte_consolidado`.
- **Nombre de archivo**: `PC_{EMPRESA}_{YYYYMM}_v{N}_{FINAL|PRELIMINAR}.{csv|json}` (también en las cabeceras `X-Export-Estado` y `X-Export-Version`).
- Sólo se emiten líneas con cantidad (o monto) distinta de 0.
- Columna `monto` (S/, 2 decimales): sólo la llena B3AM con el monto aprobado; vacía en los demás conceptos.
- El estado `FINAL` sólo se emite con el periodo cerrado (`solo_cerrado=true` devuelve 409 si está abierto).

## Catálogo de conceptos
| Código | Descripción | Unidad | Tipo |
|---|---|---|---|
| HN | Horas normales trabajadas (trabajadas − HE) | HORAS | INFORMATIVO |
| TAR | Tardanza | MINUTOS | DESCUENTO |
| HE25 | Horas extra 25% | HORAS | REMUNERATIVO |
| HE35 | Horas extra 35% | HORAS | REMUNERATIVO |
| HNOC | Horas nocturnas (etiqueta con la ventana configurada, p. ej. 22:00-06:00; siempre se calculan) | HORAS | INFORMATIVO |
| RNOC | Recargo nocturno — **sólo** empresas con `nocturno.mostrar_sobretasa_separada` (CAVAS sí, GCB SA no) | HORAS | REMUNERATIVO |
| B3AM | Bono nocturno 3 AM (interno, no es el recargo nocturno legal): cantidad y **monto S/** aprobados (registra admin, aprueba otra persona RRHH/admin) | CANTIDAD | INGRESO_INTERNO |
| BHCRE | Banco de horas: créditos del mes | HORAS | INFORMATIVO |
| BHDEB | Banco de horas: débitos del mes (descansos, expiraciones) | HORAS | INFORMATIVO |
| BHSAL | Saldo del banco de horas al último día del mes | HORAS | INFORMATIVO |

## CSV (UTF-8 sin BOM, separador `;`, punto decimal, una línea por trabajador × concepto)
```
layout_version;empresa_codigo;empresa_ruc;periodo;estado;version_archivo;trabajador_codigo;doc_tipo;doc_numero;concepto_codigo;concepto_tipo;unidad;cantidad;monto
PC-ASIS-1.1;CAVAS;20123456789;2026-10;PRELIMINAR;1;CAV-007;DNI;40000007;HE25;REMUNERATIVO;HORAS;3.0;
PC-ASIS-1.1;CAVAS;20123456789;2026-10;PRELIMINAR;1;CAV-007;DNI;40000007;RNOC;REMUNERATIVO;HORAS;14.0;
PC-ASIS-1.1;CAVAS;20123456789;2026-10;PRELIMINAR;1;CAV-007;DNI;40000007;B3AM;INGRESO_INTERNO;CANTIDAD;2;60.00
```

## JSON
```json
{
  "layout_version": "PC-ASIS-1.1", "empresa_codigo": "CAVAS", "empresa_ruc": "20123456789",
  "periodo": "2026-10", "estado": "FINAL", "version_archivo": 2, "generado_en": "2026-11-01T14:00:00+00:00",
  "conceptos": {"HE25": {"descripcion": "Horas extra 25%", "unidad": "HORAS", "tipo": "REMUNERATIVO"}},
  "lineas": [{"trabajador_codigo": "CAV-007", "doc_tipo": "DNI", "doc_numero": "40000007",
              "trabajador_nombre": "…", "concepto_codigo": "HE25", "concepto_tipo": "REMUNERATIVO",
              "unidad": "HORAS", "cantidad": 3.0, "monto": null}]
}
```
`generado_en` está en UTC. Cambios incompatibles del layout incrementan `layout_version` (p. ej. `PC-ASIS-2.0`).
## Historial de versiones

- `PC-ASIS-1.0`: layout inicial (sólo cantidades).
- `PC-ASIS-1.1` (Sprint 3, Inc. 4): columna final `monto` (aditiva); B3AM lleva el monto aprobado en S/.
- Sprint 7: conceptos aditivos BHCRE/BHDEB, validación contra contrato, checksum, versiones persistidas, export por lote (trabajo en segundo plano).
