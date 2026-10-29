# Layout de Exportación de Reportes - Sprint 3

## Consolidado Mensual (Excel/CSV)

### Columnas

El reporte `consolidado-mensual` genera archivos Excel (.xlsx) y CSV con el siguiente layout:

| Columna | Descripción | Tipo | Notas |
|---------|-------------|------|-------|
| Código | Código único del trabajador | String | Ej: CAV-007, GCB-023 |
| Nombres | Nombres del trabajador | String | |
| Apellidos | Apellidos del trabajador | String | |
| Horas Trabajadas | Total de horas trabajadas en el mes | Decimal | Sumado de asistencia diaria |
| Tardanza (min) | Total de minutos de tardanza en el mes | Integer | Sumado de todas las tardanzas |
| HE 25% | Horas extra al 25% | Decimal | Primeras 2 horas diarias |
| HE 35% | Horas extra al 35% | Decimal | A partir de la 3ra hora diaria |
| Horas Nocturnas | Horas trabajadas en turno nocturno (10 PM - 6 AM) | Decimal | Para recargo nocturno |
| Bono 3 AM | Cantidad de cierres de turno a las 3 AM | Integer | Concepto separado de ingreso |
| Ausencias | Número de días sin marca de asistencia | Integer | Faltas no justificadas |

### Formato de Archivo

**Excel (.xlsx)**
- Nombre: `consolidado_YYYY-MM.xlsx`
- Hoja: "Consolidado YYYY-MM"
- Encabezados en negrita en la primera fila
- Números con 2 decimales

**CSV**
- Nombre: `consolidado_YYYY-MM.csv`
- Codificación: UTF-8
- Separador: coma (,)
- Sin comillas alrededor de valores numéricos

### Ejemplo

```
Código,Nombres,Apellidos,Horas Trabajadas,Tardanza (min),HE 25%,HE 35%,Horas Nocturnas,Bono 3 AM,Ausencias
CAV-007,Juan,Pérez,176.5,15,4.5,2.0,8.0,3,0
CAV-023,María,García,180.0,0,0.0,0.0,0.0,0,1
```

## Conceptos Remunerativos (JSON)

El endpoint `/reportes/conceptos-remunerativos` devuelve JSON con el formato para integración con Planilla Core:

```json
{
  "periodo": "2026-10",
  "empresa_id": 1,
  "empresa_codigo": "CAVAS",
  "trabajadores": [
    {
      "trabajador_codigo": "CAV-007",
      "trabajador_nombre": "Juan Pérez",
      "he_25_horas": 4.5,
      "he_35_horas": 2.0,
      "bono_3am_cantidad": 3,
      "recargo_nocturno_horas": 8.0
    }
  ]
}
```

### Notas Importantes

1. **Bono 3 AM**: Se exporta como **línea de ingreso separada** en Planilla Core, no como parte del salario base.

2. **Recargo Nocturno**: 
   - Solo se incluye la columna `recargo_nocturno_horas` para empresas configuradas
   - CAVAS: **SÍ** incluye recargo nocturno
   - GCB SA: **NO** incluye recargo nocturno
   - La configuración se maneja a nivel de empresa

3. **Horas Extra**:
   - HE 25%: Primeras 2 horas extra diarias o trabajo en día de descanso
   - HE 35%: A partir de la 3ra hora extra o trabajo en feriado

4. **Periodo Operativo**: El periodo (`YYYY-MM`) corresponde al mes operativo, que puede diferir del mes calendario según la fecha de corte de planilla.

## Integración con Planilla Core

Los archivos exportados están diseñados para carga directa en el sistema de nómina:

1. Descargar archivo Excel/CSV desde el endpoint `/reportes/consolidado-mensual`
2. Importar en módulo de conceptos remunerativos de Planilla Core
3. Validar totales antes de procesar nómina
4. El bono 3 AM debe cargarse como concepto separado (código específico según empresa)

## Auditoría

Todos los exports generan registros de auditoría que incluyen:
- Usuario que generó el reporte
- Timestamp de generación
- Parámetros utilizados (periodo, empresa, formato)
- Número de registros exportados

## Versiones

- Sprint 3 (Octubre 2026): Layout inicial con soporte Excel/CSV
- Próximos sprints: Agregar conceptos adicionales según normativa laboral
