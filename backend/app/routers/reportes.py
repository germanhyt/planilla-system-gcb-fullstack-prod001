"""Sprint 3: Reportes consolidados y export a Excel/CSV."""
from io import BytesIO, StringIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Asistencia, BonoNocturno, Empresa, Trabajador, Usuario

router = APIRouter(prefix="/reportes", tags=["reportes"])


def _consolidado_mensual_data(
    db: Session, 
    periodo: str,
    empresa_id: Optional[int],
    unidad_id: Optional[int],
    trabajador_id: Optional[int],
):
    """Lógica central: construir consolidado mensual desde tabla asistencia."""
    q = db.query(
        Trabajador.id.label("trabajador_id"),
        Trabajador.codigo,
        Trabajador.nombres,
        Trabajador.apellidos,
        Trabajador.empresa_id,
        Trabajador.unidad_id,
        Asistencia.periodo,
        Asistencia.horas_trabajadas,
        Asistencia.tardanza_min,
        Asistencia.horas_extra_25,
        Asistencia.horas_extra_35,
        Asistencia.horas_nocturnas,
    ).join(
        Asistencia, Asistencia.trabajador_id == Trabajador.id
    ).filter(
        Asistencia.periodo == periodo
    )
    
    if empresa_id:
        q = q.filter(Trabajador.empresa_id == empresa_id)
    if unidad_id:
        q = q.filter(Trabajador.unidad_id == unidad_id)
    if trabajador_id:
        q = q.filter(Trabajador.id == trabajador_id)
    
    rows = q.all()
    
    # Agrupar por trabajador
    from collections import defaultdict
    trabajadores_data = defaultdict(lambda: {
        "trabajador_id": 0,
        "codigo": "",
        "nombres": "",
        "apellidos": "",
        "empresa_id": 0,
        "unidad_id": 0,
        "horas_trabajadas": 0.0,
        "tardanza_min": 0,
        "horas_extra_25": 0.0,
        "horas_extra_35": 0.0,
        "horas_nocturnas": 0.0,
        "ausencias": 0,
    })
    
    for row in rows:
        tid = row.trabajador_id
        trabajadores_data[tid]["trabajador_id"] = row.trabajador_id
        trabajadores_data[tid]["codigo"] = row.codigo
        trabajadores_data[tid]["nombres"] = row.nombres
        trabajadores_data[tid]["apellidos"] = row.apellidos
        trabajadores_data[tid]["empresa_id"] = row.empresa_id
        trabajadores_data[tid]["unidad_id"] = row.unidad_id
        
        # Acumular totales
        trabajadores_data[tid]["horas_trabajadas"] += float(row.horas_trabajadas or 0)
        trabajadores_data[tid]["tardanza_min"] += row.tardanza_min
        trabajadores_data[tid]["horas_extra_25"] += float(row.horas_extra_25 or 0)
        trabajadores_data[tid]["horas_extra_35"] += float(row.horas_extra_35 or 0)
        trabajadores_data[tid]["horas_nocturnas"] += float(row.horas_nocturnas or 0)
        
        # Contar ausencias (días sin marca)
        if not row.horas_trabajadas or row.horas_trabajadas == 0:
            trabajadores_data[tid]["ausencias"] += 1
    
    # Agregar bonos nocturnos 3 AM
    bonos = db.query(
        BonoNocturno.trabajador_id,
        BonoNocturno.cantidad
    ).filter(
        BonoNocturno.periodo == periodo,
        BonoNocturno.estado == "aprobado"
    ).all()
    
    bonos_dict = {b.trabajador_id: b.cantidad for b in bonos}
    
    for tid in trabajadores_data:
        trabajadores_data[tid]["bono_3am"] = bonos_dict.get(tid, 0)
    
    return list(trabajadores_data.values())


@router.get("/consolidado-mensual")
def consolidado_mensual(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    empresa_id: Optional[int] = None,
    unidad_id: Optional[int] = None,
    trabajador_id: Optional[int] = None,
    formato: str = Query("json", pattern=r"^(json|excel|csv)$"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """
    Consolidado mensual por trabajador con totales de horas, tardanzas, HE, horas nocturnas y bono 3 AM.
    Export a Excel o CSV con layout documentado para Planilla Core.
    """
    if user.rol not in ("rrhh", "admin", "jefe"):
        raise HTTPException(403, "No autorizado")
    
    # Jefe solo ve su unidad
    if user.rol == "jefe" and not unidad_id:
        unidad_id = user.unidad_id
    
    registros = _consolidado_mensual_data(db, periodo, empresa_id, unidad_id, trabajador_id)
    
    if formato == "json":
        totales = {
            "total_trabajadores": len(registros),
            "total_horas_trabajadas": sum(r["horas_trabajadas"] for r in registros),
            "total_horas_extra_25": sum(r["horas_extra_25"] for r in registros),
            "total_horas_extra_35": sum(r["horas_extra_35"] for r in registros),
            "total_horas_nocturnas": sum(r["horas_nocturnas"] for r in registros),
            "total_bono_3am": sum(r.get("bono_3am", 0) for r in registros),
        }
        return {"periodo": periodo, "registros": registros, "totales": totales}
    
    elif formato == "excel":
        # Generar Excel con openpyxl
        try:
            from openpyxl import Workbook
        except ImportError:
            raise HTTPException(500, "openpyxl no instalado") from None
        
        wb = Workbook()
        ws = wb.active
        ws.title = f"Consolidado {periodo}"
        
        # Encabezados
        headers = [
            "Código", "Nombres", "Apellidos", "Horas Trabajadas",
            "Tardanza (min)", "HE 25%", "HE 35%", "Horas Nocturnas",
            "Bono 3 AM", "Ausencias"
        ]
        ws.append(headers)
        
        # Datos
        for r in registros:
            ws.append([
                r["codigo"],
                r["nombres"],
                r["apellidos"],
                round(r["horas_trabajadas"], 2),
                r["tardanza_min"],
                round(r["horas_extra_25"], 2),
                round(r["horas_extra_35"], 2),
                round(r["horas_nocturnas"], 2),
                r.get("bono_3am", 0),
                r["ausencias"]
            ])
        
        # Guardar en BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=consolidado_{periodo}.xlsx"
            }
        )
    
    elif formato == "csv":
        import csv
        output = StringIO()
        
        # Escribir CSV en memoria
        writer = csv.writer(output)
        writer.writerow([
            "Código", "Nombres", "Apellidos", "Horas Trabajadas",
            "Tardanza (min)", "HE 25%", "HE 35%", "Horas Nocturnas",
            "Bono 3 AM", "Ausencias"
        ])
        
        for r in registros:
            writer.writerow([
                r["codigo"],
                r["nombres"],
                r["apellidos"],
                round(r["horas_trabajadas"], 2),
                r["tardanza_min"],
                round(r["horas_extra_25"], 2),
                round(r["horas_extra_35"], 2),
                round(r["horas_nocturnas"], 2),
                r.get("bono_3am", 0),
                r["ausencias"]
            ])
        
        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=consolidado_{periodo}.csv"
            }
        )


@router.get("/conceptos-remunerativos")
def conceptos_remunerativos(
    periodo: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    empresa_id: int = Query(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """
    Export de conceptos remunerativos para integración con Planilla Core.
    Formato: trabajador + HE 25 + HE 35 + bono 3 AM (línea aparte) + recargo nocturno (según flag empresa).
    """
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    
    # Obtener configuración empresa
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(404, "Empresa no encontrada")
    
    registros = _consolidado_mensual_data(db, periodo, empresa_id, None, None)
    
    trabajadores_export = []
    for r in registros:
        conceptos = {
            "trabajador_codigo": r["codigo"],
            "trabajador_nombre": f"{r['nombres']} {r['apellidos']}",
            "he_25_horas": round(r["horas_extra_25"], 2),
            "he_35_horas": round(r["horas_extra_35"], 2),
            "bono_3am_cantidad": r.get("bono_3am", 0),
        }
        
        # Recargo nocturno: solo para empresas configuradas (CAVAS sí, GCB SA no)
        # Esta lógica se ajusta según reglas de negocio reales
        if empresa.codigo == "CAVAS":
            conceptos["recargo_nocturno_horas"] = round(r["horas_nocturnas"], 2)
        
        trabajadores_export.append(conceptos)
    
    return {
        "periodo": periodo,
        "empresa_id": empresa_id,
        "empresa_codigo": empresa.codigo,
        "trabajadores": trabajadores_export
    }
