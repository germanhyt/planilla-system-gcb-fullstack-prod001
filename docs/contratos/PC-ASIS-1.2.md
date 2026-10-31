# Contrato de interfaz `PC-ASIS-1.2` (Asistencia → Planilla Core)

Estado: **vigente** desde Sprint 7. Fuente de verdad ejecutable: `backend/app/export_pc.py` (modelos pydantic
`ExportPC` / `LineaPC` / `ConceptoPC`, `extra=forbid`) y su JSON Schema generado
`backend/app/contracts/pc_asis_1_2.schema.json` (también en `GET /api/reportes/export-planilla-core/contrato`).
Un test (`test_s7_planilla_core.py`) falla si el schema publicado deja de coincidir con el modelo.

## Validación
Todo export se valida contra el contrato **antes** de persistirse; si no cumple, no se genera archivo ni versión.

## Granularidad
Un archivo por **empresa + periodo (YYYY-MM) + formato (csv|json)**. El lote
(`POST /reportes/export-planilla-core/lote`) genera un archivo por empresa del alcance del usuario.

## Versionado e idempotencia
- Cada export queda guardado byte a byte en `export_planilla` (versión, checksum, contenido, nº trabajadores/líneas).
- `version_archivo` es correlativa por empresa+periodo (común a csv y json) y continúa la numeración de auditoría previa a S7.
- **Re-export idempotente**: si el checksum coincide con la última versión del mismo formato, no se crea versión nueva;
  se devuelve la existente con `X-Export-Reutilizada: 1` y se audita `reexportar_sin_cambios`.
- Historial: `GET /reportes/export-planilla-core/versiones?empresa_id=&periodo=`; descarga exacta: `GET .../versiones/{id}`.

## Checksum
`sha256` (hex) del JSON canónico (claves ordenadas, sin espacios, UTF-8) de
`{layout_version, empresa_codigo, empresa_ruc, periodo, estado, lineas}`. Excluye `version_archivo` y `generado_en`,
de modo que dos exports con los mismos datos tienen el mismo checksum. Cabeceras: `X-Export-Checksum`, `X-Export-Version`,
`X-Export-Estado`, `X-Export-Reutilizada`.

## Conceptos
HN, TAR, HE25, HE35, HNOC (etiqueta con la ventana nocturna configurada, p. ej. `Horas nocturnas 22:00-06:00`),
RNOC (sólo empresas con sobretasa separada), B3AM (cantidad + monto S/ aprobado),
**BHCRE** (créditos del banco de horas en el mes), **BHDEB** (débitos: descansos y expiraciones), BHSAL (saldo al cierre del mes).

## Compatibilidad
- Cambios **aditivos** (nuevos códigos de concepto, campos opcionales) mantienen `PC-ASIS-1.x`; el consumidor debe ignorar
  conceptos que no conoce. Aun así, por decisión del PO (pt57u) la incorporación de BHCRE/BHDEB sube el layout a 1.2.
- Cambios incompatibles (renombrar/quitar columnas, cambiar tipos o semántica) suben a `PC-ASIS-2.0`.
- `PC-ASIS-1.2` (Sprint 7, PO pt57u): versión vigente. Igual a 1.1 + conceptos BHCRE/BHDEB. Como el checksum incluye `layout_version`, el primer export 1.2 de un periodo ya exportado en 1.1 genera una versión nueva del archivo.
