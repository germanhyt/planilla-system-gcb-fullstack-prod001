"""Sprint 3: Reportes consolidados y export a Excel/CSV."""
from datetime import datetime
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..audit import audit
from ..db import get_db
from ..deps import current_user, require
from ..models import Asistencia, BonoNocturno, Empresa, Marca, Trabajador, TurnoPlantilla, Unidad, Usuario

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/consolidado-mensual")
async def consolidado_mensual(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    empresa_id: Optional[int] = None,
    unidad_id: Optional[int] = None,
    trabajador_id: Optional[int] = None,
    formato: str = Query("json", pattern=r"^(json|excel|csv)$"),
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Consolidado mensual por trabajador con totales de horas.
    Filtrable por empresa, unidad o trabajador específico.
    Soporta export a JSON, Excel y CSV.
    """
    if user.rol not in ("rrhh", "admin"):
        if user.rol == "jefe":
            if not user.unidad_id:
                raise HTTPException(403, "Jefe sin unidad asignada")
            unidad_id = user.unidad_id
        else:
            raise HTTPException(403, "No autorizado para ver reportes")
    
    q = (
        select(
            Asistencia,
            Trabajador,
            Empresa,
            Unidad,
            TurnoPlantilla,
            Marca.alias("entrada_marca"),
            Marca.alias("salida_marca"),
        )
        .join(Trabajador, Asistencia.trabajador_id == Trabajador.id)
        .join(Empresa, Trabajador.empresa_id == Empresa.id)
        .join(Unidad, Trabajador.unidad_id == Unidad.id)
        .outerjoin(TurnoPlantilla, Asistencia.turno_plantilla_id == TurnoPlantilla.id)
        .outerjoin(Marca, Asistencia.entrada_marca_id == Marca.id, isouter=True)
        .outerjoin(Marca, Asistencia.salida_marca_id == Marca.id, isouter=True)
        .where(Asistencia.periodo == periodo)
    )
    
    if empresa_id:
        q = q.where(Empresa.id == empresa_id)
    if unidad_id:
        q = q.where(Unidad.id == unidad_id)
    if trabajador_id:
        q = q.where(Trabajador.id == trabajador_id)
    
    q = q.order_by(Trabajador.codigo, Asistencia.dia_operativo)
    result = await db.execute(q)
    rows = result.all()
    
    if not rows:
        raise HTTPException(404, f"Sin registros de asistencia para periodo {periodo}")
    
    data = []
    for row in rows:
        asist, trab, emp, uni, turno, entrada, salida = row[:7]
        data.append({
            "trabajador_codigo": trab.codigo,
            "trabajador_nombre": f"{trab.nombres} {trab.apellidos}",
            "empresa": emp.razon_social,
            "unidad": uni.nombre,
            "dia": asist.dia_operativo.isoformat(),
            "turno": turno.nombre if turno else None,
            "entrada": entrada.ts_servidor.isoformat() if entrada else None,
            "salida": salida.ts_servidor.isoformat() if salida else None,
            "horas_programadas": float(asist.horas_programadas) if asist.horas_programadas else 0,
            "horas_trabajadas": float(asist.horas_trabajadas) if asist.horas_trabajadas else 0,
            "tardanza_min": asist.tardanza_min,
            "he_25": float(asist.horas_extra_25),
            "he_35": float(asist.horas_extra_35),
            "nocturnas": float(asist.horas_nocturnas),
        })
    
    trabajadores_ids = list({row[1].id for row in rows})
    totales_por_trabajador = {}
    for tid in trabajadores_ids:
        q_tot = (
            select(
                func.sum(Asistencia.horas_trabajadas).label("total_trabajadas"),
                func.sum(Asistencia.horas_extra_25).label("total_he25"),
                func.sum(Asistencia.horas_extra_35).label("total_he35"),
                func.sum(Asistencia.horas_nocturnas).label("total_nocturnas"),
                func.sum(Asistencia.tardanza_min).label("total_tardanzas"),
            )
            .where(and_(Asistencia.trabajador_id == tid, Asistencia.periodo == periodo))
        )
        tot_result = await db.execute(q_tot)
        tot = tot_result.first()
        totales_por_trabajador[tid] = {
            "horas_trabajadas": float(tot.total_trabajadas or 0),
            "he_25": float(tot.total_he25 or 0),
            "he_35": float(tot.total_he35 or 0),
            "nocturnas": float(tot.total_nocturnas or 0),
            "tardanzas_min": int(tot.total_tardanzas or 0),
        }
    
    resultado = {
        "periodo": periodo,
        "registros": data,
        "totales": totales_por_trabajador,
    }
    
    await auditar(
        db,
        usuario_id=user.id,
        accion="ver_reporte_consolidado",
        entidad="asistencia",
        entidad_id=periodo,
    )
    
    if formato == "json":
        return resultado
    elif formato == "excel":
        excel_bytes = generar_excel_consolidado(resultado, periodo)
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=consolidado_{periodo}.xlsx"}
        )
    elif formato == "csv":
        csv_content = generar_csv_consolidado(resultado)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=consolidado_{periodo}.csv"}
        )


@router.get("/conceptos-remunerativos")
async def conceptos_remunerativos(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    empresa_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """
    Export estructurado para integración con sistema de nómina.
    Solo para RRHH/Admin. Incluye bono 3 AM separado.
    """
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    q = (
        select(
            Trabajador.codigo,
            Trabajador.nombres,
            Trabajador.apellidos,
            func.sum(Asistencia.horas_trabajadas).label("horas_ordinarias"),
            func.sum(Asistencia.horas_extra_25).label("he_25"),
            func.sum(Asistencia.horas_extra_35).label("he_35"),
            func.sum(Asistencia.horas_nocturnas).label("nocturnas"),
            func.sum(Asistencia.tardanza_min).label("tardanzas_min"),
        )
        .join(Trabajador, Asistencia.trabajador_id == Trabajador.id)
        .where(
            and_(
                Asistencia.periodo == periodo,
                Trabajador.empresa_id == empresa_id,
            )
        )
        .group_by(Trabajador.id, Trabajador.codigo, Trabajador.nombres, Trabajador.apellidos)
    )
    result = await db.execute(q)
    trabajadores = result.all()
    
    q_bonos = (
        select(Trabajador.codigo, BonoNocturno.cantidad)
        .join(Trabajador, BonoNocturno.trabajador_id == Trabajador.id)
        .where(
            and_(
                BonoNocturno.periodo == periodo,
                Trabajador.empresa_id == empresa_id,
                BonoNocturno.estado == "aprobado",
            )
        )
    )
    bonos_result = await db.execute(q_bonos)
    bonos_dict = {codigo: cant for codigo, cant in bonos_result.all()}
    
    conceptos = []
    for row in trabajadores:
        conceptos.append({
            "codigo": row.codigo,
            "nombre_completo": f"{row.nombres} {row.apellidos}",
            "conceptos": {
                "horas_ordinarias": float(row.horas_ordinarias or 0),
                "he_25": float(row.he_25 or 0),
                "he_35": float(row.he_35 or 0),
                "nocturnas": float(row.nocturnas or 0),
                "tardanzas_min": int(row.tardanzas_min or 0),
                "bono_3am": bonos_dict.get(row.codigo, 0),
            }
        })
    
    await auditar(
        db,
        usuario_id=user.id,
        accion="export_conceptos_remunerativos",
        entidad="asistencia",
        entidad_id=f"{empresa_id}_{periodo}",
    )
    
    return {
        "periodo": periodo,
        "empresa_id": empresa_id,
        "trabajadores": conceptos,
    }


def generar_excel_consolidado(resultado: dict, periodo: str) -> bytes:
    """Genera archivo Excel con formato para integración con Planilla Core."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        raise HTTPException(500, "openpyxl no disponible para export Excel")
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Consolidado {periodo}"
    
    headers = [
        "Código", "Trabajador", "Empresa", "Unidad", "Día",
        "Turno", "Entrada", "Salida", "H. Programadas", "H. Trabajadas",
        "Tardanza (min)", "HE 25%", "HE 35%", "Nocturnas"
    ]
    ws.append(headers)
    
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
    
    for reg in resultado["registros"]:
        ws.append([
            reg["trabajador_codigo"],
            reg["trabajador_nombre"],
            reg["empresa"],
            reg["unidad"],
            reg["dia"],
            reg["turno"],
            reg["entrada"],
            reg["salida"],
            reg["horas_programadas"],
            reg["horas_trabajadas"],
            reg["tardanza_min"],
            reg["he_25"],
            reg["he_35"],
            reg["nocturnas"],
        ])
    
    ws_resumen = wb.create_sheet("Resumen")
    ws_resumen.append(["Código Trabajador", "H. Trabajadas", "HE 25%", "HE 35%", "Nocturnas", "Tardanzas (min)"])
    for cell in ws_resumen[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
    
    for tid, tot in resultado["totales"].items():
        ws_resumen.append([
            str(tid),
            tot["horas_trabajadas"],
            tot["he_25"],
            tot["he_35"],
            tot["nocturnas"],
            tot["tardanzas_min"],
        ])
    
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def generar_csv_consolidado(resultado: dict) -> bytes:
    """Genera archivo CSV simple."""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        "Código", "Trabajador", "Empresa", "Unidad", "Día",
        "Turno", "Entrada", "Salida", "H. Programadas", "H. Trabajadas",
        "Tardanza (min)", "HE 25%", "HE 35%", "Nocturnas"
    ])
    
    for reg in resultado["registros"]:
        writer.writerow([
            reg["trabajador_codigo"],
            reg["trabajador_nombre"],
            reg["empresa"],
            reg["unidad"],
            reg["dia"],
            reg["turno"] or "",
            reg["entrada"] or "",
            reg["salida"] or "",
            reg["horas_programadas"],
            reg["horas_trabajadas"],
            reg["tardanza_min"],
            reg["he_25"],
            reg["he_35"],
            reg["nocturnas"],
        ])
    
    return output.getvalue().encode("utf-8")
