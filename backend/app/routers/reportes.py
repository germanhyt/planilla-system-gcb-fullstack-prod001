"""Sprint 3: reportes consolidados (pantalla Reportes) y exportación a Planilla Core.

- Periodo = mes calendario YYYY-MM; cada día se asigna por su *día operativo* (un turno 22:00-06:00 que
  empieza el 31 cuenta en el mes del 31).
- Recargo nocturno: se muestra aparte sólo si la empresa lo tiene configurado
  (rule_set `nocturno.mostrar_sobretasa_separada`: CAVAS sí, GCB SA no). Las horas 22-06 siempre se calculan.
- Bono nocturno 3 AM: concepto interno (no es el recargo legal); se exporta la cantidad y el monto (S/) aprobados
  por administración como ingreso separado (concepto B3AM).
- Jefe: sólo su unidad. RRHH/admin: todo.
"""
import csv
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from io import BytesIO, StringIO
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..alcance import empresa_alcance
from ..audit import audit
from ..db import get_db
from ..deps import current_user
from ..models import (
    Asistencia,
    Auditoria,
    BancoHorasCompensatorias,
    BonoNocturno,
    CierrePeriodo,
    Empresa,
    Trabajador,
    Usuario,
)

router = APIRouter(prefix="/reportes", tags=["reportes"])

PERIODO = r"^\d{4}-(0[1-9]|1[0-2])$"
LAYOUT_VERSION = "PC-ASIS-1.1"  # 1.1: columna `monto` (S/) en B3AM
# Catálogo de conceptos de la interfaz con Planilla Core (ver docs/interfaz-planilla-core.md).
CONCEPTOS = {
    "HN": ("Horas normales trabajadas", "HORAS", "INFORMATIVO"),
    "TAR": ("Tardanza", "MINUTOS", "DESCUENTO"),
    "HE25": ("Horas extra 25%", "HORAS", "REMUNERATIVO"),
    "HE35": ("Horas extra 35%", "HORAS", "REMUNERATIVO"),
    "HNOC": ("Horas nocturnas 22:00-06:00", "HORAS", "INFORMATIVO"),
    "RNOC": ("Recargo nocturno (sólo empresas con sobretasa separada)", "HORAS", "REMUNERATIVO"),
    "B3AM": ("Bono nocturno 3 AM (cantidad de cierres; monto S/ aprobado por administración)", "CANTIDAD",
             "INGRESO_INTERNO"),
    "BHSAL": ("Saldo banco de horas al cierre del mes", "HORAS", "INFORMATIVO"),
}
COLUMNAS = [
    ("codigo", "Código"), ("trabajador", "Trabajador"), ("empresa", "Empresa"), ("horas_trabajadas", "Horas trabajadas"),
    ("horas_normales", "Horas normales"), ("tardanza_min", "Tardanza (min)"), ("horas_extra_25", "HE 25%"),
    ("horas_extra_35", "HE 35%"), ("horas_nocturnas", "Horas nocturnas 22-06"),
    ("recargo_nocturno_horas", "Recargo nocturno (h)"), ("bono_3am", "Bono 3 AM (cant.)"),
    ("bono_3am_monto", "Bono 3 AM (S/)"),
    ("banco_horas_mes", "Banco horas mov. mes"), ("banco_horas_saldo", "Banco horas saldo"), ("ausencias", "Ausencias"),
]


def rango(periodo: str) -> tuple[date, date]:
    anio, mes = map(int, periodo.split("-"))
    fin = date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)
    return date(anio, mes, 1), fin - timedelta(days=1)


def recargo_separado(db: Session, empresa_id: int, dia: date) -> bool:
    from .bandeja import _reglas
    return bool(_reglas(db, empresa_id, dia)["nocturno"].get("mostrar_sobretasa_separada"))


def periodo_cerrado(db: Session, empresa_id: int, periodo: str) -> bool:
    return db.query(CierrePeriodo).filter(CierrePeriodo.empresa_id == empresa_id, CierrePeriodo.periodo == periodo,
                                          CierrePeriodo.estado == "cerrado").first() is not None


def _unidad_alcance(user: Usuario, unidad_id: Optional[int]) -> Optional[int]:
    if user.rol not in ("rrhh", "admin", "jefe"):
        raise HTTPException(403, "No autorizado")
    if user.rol == "jefe":
        if not user.unidad_id:
            raise HTTPException(403, "Jefe sin unidad asignada")
        if unidad_id and unidad_id != user.unidad_id:
            raise HTTPException(403, "Sólo puede consultar su unidad")
        return user.unidad_id
    return unidad_id


def _r2(x) -> float:
    return round(float(x or 0), 2)


def _consolidado_mensual_data(db: Session, periodo: str, empresa_id: Optional[int], unidad_id: Optional[int],
                              trabajador_id: Optional[int]) -> list[dict]:
    """Totales del mes por trabajador desde `asistencia` (por día operativo) + bono 3 AM + banco de horas."""
    desde, hasta = rango(periodo)
    q = db.query(Trabajador, Asistencia).join(Asistencia, Asistencia.trabajador_id == Trabajador.id).filter(
        Asistencia.dia_operativo >= desde, Asistencia.dia_operativo <= hasta)
    if empresa_id:
        q = q.filter(Trabajador.empresa_id == empresa_id)
    if unidad_id:
        q = q.filter(Trabajador.unidad_id == unidad_id)
    if trabajador_id:
        q = q.filter(Trabajador.id == trabajador_id)
    empresas = {e.id: e for e in db.query(Empresa).all()}
    flags: dict[int, bool] = {}
    data: dict[int, dict] = {}

    def nueva(t):
        if t.empresa_id not in flags:
            flags[t.empresa_id] = recargo_separado(db, t.empresa_id, desde)
        emp = empresas.get(t.empresa_id)
        data[t.id] = {
            "trabajador_id": t.id, "codigo": t.codigo, "nombres": t.nombres, "apellidos": t.apellidos,
            "trabajador": f"{t.nombres} {t.apellidos}", "doc_tipo": t.doc_tipo, "doc_numero": t.doc_numero,
            "empresa_id": t.empresa_id, "empresa": emp.codigo if emp else None, "unidad_id": t.unidad_id,
            "horas_trabajadas": 0.0, "tardanza_min": 0, "horas_extra_25": 0.0, "horas_extra_35": 0.0,
            "horas_nocturnas": 0.0, "ausencias": 0, "dias_trabajados": 0, "_recargo": flags[t.empresa_id]}
        return data[t.id]

    for t, a in q.order_by(Trabajador.codigo, Asistencia.dia_operativo).all():
        r = data.get(t.id) or nueva(t)
        r["horas_trabajadas"] += float(a.horas_trabajadas or 0)
        r["tardanza_min"] += int(a.tardanza_min or 0)
        r["horas_extra_25"] += float(a.horas_extra_25 or 0)
        r["horas_extra_35"] += float(a.horas_extra_35 or 0)
        r["horas_nocturnas"] += float(a.horas_nocturnas or 0)
        if a.horas_trabajadas:
            r["dias_trabajados"] += 1
        else:
            r["ausencias"] += 1
    # Trabajadores con bono 3 AM aprobado pero sin asistencia en el mes: igual deben salir (ingreso separado).
    qb = db.query(Trabajador).join(BonoNocturno, BonoNocturno.trabajador_id == Trabajador.id).filter(
        BonoNocturno.periodo == periodo, BonoNocturno.estado == "aprobado")
    if empresa_id:
        qb = qb.filter(Trabajador.empresa_id == empresa_id)
    if unidad_id:
        qb = qb.filter(Trabajador.unidad_id == unidad_id)
    if trabajador_id:
        qb = qb.filter(Trabajador.id == trabajador_id)
    for t in qb.order_by(Trabajador.codigo).all():
        if t.id not in data:
            nueva(t)
    if not data:
        return []
    tids = list(data)
    bonos = {tid: (cant, monto) for tid, cant, monto in db.query(
        BonoNocturno.trabajador_id, BonoNocturno.cantidad, BonoNocturno.monto).filter(
        BonoNocturno.periodo == periodo, BonoNocturno.estado == "aprobado", BonoNocturno.trabajador_id.in_(tids)).all()}
    saldo: dict[int, float] = {}
    for m in db.query(BancoHorasCompensatorias).filter(
            BancoHorasCompensatorias.trabajador_id.in_(tids), BancoHorasCompensatorias.fecha_movimiento <= hasta
    ).order_by(BancoHorasCompensatorias.fecha_movimiento, BancoHorasCompensatorias.id):
        saldo[m.trabajador_id] = float(m.saldo_nuevo)
    mov = defaultdict(float)
    for tid, tipo, h in db.query(BancoHorasCompensatorias.trabajador_id, BancoHorasCompensatorias.tipo,
                                 func.sum(BancoHorasCompensatorias.horas)).filter(
            BancoHorasCompensatorias.trabajador_id.in_(tids), BancoHorasCompensatorias.fecha_movimiento >= desde,
            BancoHorasCompensatorias.fecha_movimiento <= hasta).group_by(
            BancoHorasCompensatorias.trabajador_id, BancoHorasCompensatorias.tipo):
        mov[tid] += float(h or 0) * (1 if tipo == "credito" else -1)
    out = []
    for tid, r in data.items():
        he = r["horas_extra_25"] + r["horas_extra_35"]
        r["horas_normales"] = _r2(max(0.0, r["horas_trabajadas"] - he))
        for k in ("horas_trabajadas", "horas_extra_25", "horas_extra_35", "horas_nocturnas"):
            r[k] = _r2(r[k])
        r["recargo_nocturno_horas"] = r["horas_nocturnas"] if r.pop("_recargo") else None
        cant, monto = bonos.get(tid, (0, None))
        r["bono_3am"] = int(cant or 0)
        r["bono_3am_monto"] = _r2(monto)
        r["banco_horas_mes"] = _r2(mov.get(tid, 0))
        r["banco_horas_saldo"] = _r2(saldo.get(tid, 0))
        out.append(r)
    return sorted(out, key=lambda x: x["codigo"])


def _tabla_csv(registros: list[dict]) -> str:
    buf = StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([h for _, h in COLUMNAS])
    for r in registros:
        w.writerow(["" if r.get(k) is None else r.get(k) for k, _ in COLUMNAS])
    return buf.getvalue()


def _tabla_xlsx(registros: list[dict], titulo: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]
    ws.append([h for _, h in COLUMNAS])
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in registros:
        ws.append([r.get(k) for k, _ in COLUMNAS])
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


@router.get("/consolidado-mensual")
def consolidado_mensual(
    periodo: str = Query(..., pattern=PERIODO),
    empresa_id: Optional[int] = None,
    unidad_id: Optional[int] = None,
    trabajador_id: Optional[int] = None,
    formato: str = Query("json", pattern=r"^(json|excel|xlsx|csv)$"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Consolidado mensual por trabajador (pantalla Reportes) con descarga CSV/XLSX."""
    unidad_id = _unidad_alcance(user, unidad_id)
    empresa_id = empresa_alcance(user, empresa_id)
    registros = _consolidado_mensual_data(db, periodo, empresa_id, unidad_id, trabajador_id)
    if formato == "json":
        claves = ("horas_trabajadas", "horas_normales", "tardanza_min", "horas_extra_25", "horas_extra_35",
                  "horas_nocturnas", "bono_3am", "bono_3am_monto", "banco_horas_mes", "banco_horas_saldo")
        totales = {"total_trabajadores": len(registros)} | {
            f"total_{k}": _r2(sum(r[k] for r in registros)) for k in claves}
        totales["total_recargo_nocturno_horas"] = _r2(sum(r["recargo_nocturno_horas"] or 0 for r in registros))
        desde, hasta = rango(periodo)
        extra = {}
        if empresa_id:
            extra = {"empresa_id": empresa_id, "periodo_cerrado": periodo_cerrado(db, empresa_id, periodo),
                     "muestra_recargo_nocturno": recargo_separado(db, empresa_id, desde)}
        return {"periodo": periodo, "desde": desde.isoformat(), "hasta": hasta.isoformat(), **extra,
                "registros": registros, "totales": totales}
    nombre = f"consolidado_{periodo}" + (f"_emp{empresa_id}" if empresa_id else "")
    audit(db, user.id, "descargar", "reporte_consolidado", periodo,
          despues={"empresa_id": empresa_id, "unidad_id": unidad_id, "formato": formato, "registros": len(registros)})
    db.commit()
    if formato == "csv":
        return Response(content="\ufeff" + _tabla_csv(registros), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename={nombre}.csv"})
    return Response(content=_tabla_xlsx(registros, f"Consolidado {periodo}"),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={nombre}.xlsx"})


@router.get("/conceptos-remunerativos")
def conceptos_remunerativos(
    periodo: str = Query(..., pattern=PERIODO),
    empresa_id: int = Query(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Conceptos remunerativos por trabajador (HE 25/35, bono 3 AM aparte, recargo nocturno según empresa)."""
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    empresa_alcance(user, empresa_id)
    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(404, "Empresa no encontrada")
    trabajadores = []
    for r in _consolidado_mensual_data(db, periodo, empresa_id, None, None):
        c = {"trabajador_codigo": r["codigo"], "trabajador_nombre": r["trabajador"], "he_25_horas": r["horas_extra_25"],
             "he_35_horas": r["horas_extra_35"], "bono_3am_cantidad": r["bono_3am"],
             "bono_3am_monto": r["bono_3am_monto"]}
        if r["recargo_nocturno_horas"] is not None:
            c["recargo_nocturno_horas"] = r["recargo_nocturno_horas"]
        trabajadores.append(c)
    return {"periodo": periodo, "empresa_id": empresa_id, "empresa_codigo": empresa.codigo, "trabajadores": trabajadores}


def _lineas(registros: list[dict]) -> list[dict]:
    lineas = []
    for r in registros:
        valores = [("HN", r["horas_normales"]), ("TAR", r["tardanza_min"]), ("HE25", r["horas_extra_25"]),
                   ("HE35", r["horas_extra_35"]), ("HNOC", r["horas_nocturnas"])]
        if r["recargo_nocturno_horas"] is not None:
            valores.append(("RNOC", r["recargo_nocturno_horas"]))
        valores += [("B3AM", r["bono_3am"]), ("BHSAL", r["banco_horas_saldo"])]
        for cod, cant in valores:
            monto = r["bono_3am_monto"] if cod == "B3AM" else None
            if not cant and not monto:
                continue
            desc, unidad, tipo = CONCEPTOS[cod]
            lineas.append({"trabajador_codigo": r["codigo"], "doc_tipo": r["doc_tipo"], "doc_numero": r["doc_numero"],
                           "trabajador_nombre": r["trabajador"], "concepto_codigo": cod, "concepto_tipo": tipo,
                           "unidad": unidad, "cantidad": cant, "monto": monto})
    return lineas


@router.post("/export-planilla-core")
def export_planilla_core(
    periodo: str = Query(..., pattern=PERIODO),
    empresa_id: int = Query(...),
    formato: Literal["csv", "json"] = "csv",
    solo_cerrado: bool = False,
    db: Session = Depends(get_db),
    user: Usuario = Depends(current_user),
):
    """Archivo de interfaz versionado para Planilla Core (layout `PC-ASIS-1.1`, docs/interfaz-planilla-core.md).

    Periodo cerrado -> estado FINAL. Abierto -> se exporta marcado PRELIMINAR (o 409 si `solo_cerrado=true`).
    Cada exportación queda en auditoría y numera su versión (v1, v2...) por empresa+periodo.
    """
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    empresa_alcance(user, empresa_id)
    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(404, "Empresa no encontrada")
    cerrado = periodo_cerrado(db, empresa_id, periodo)
    if solo_cerrado and not cerrado:
        raise HTTPException(409, "El periodo no está cerrado; cierre el periodo o exporte como preliminar")
    estado = "FINAL" if cerrado else "PRELIMINAR"
    clave = f"{empresa.codigo}:{periodo}"
    version = (db.scalar(select(func.count(Auditoria.id)).where(
        Auditoria.entidad == "export_planilla_core", Auditoria.entidad_id == clave)) or 0) + 1
    registros = _consolidado_mensual_data(db, periodo, empresa_id, None, None)
    lineas = _lineas(registros)
    generado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    archivo = f"PC_{empresa.codigo}_{periodo.replace('-', '')}_v{version}_{estado}.{formato}"
    meta = {"layout_version": LAYOUT_VERSION, "empresa_codigo": empresa.codigo, "empresa_ruc": empresa.ruc,
            "periodo": periodo, "estado": estado, "version_archivo": version, "generado_en": generado}
    audit(db, user.id, "exportar", "export_planilla_core", clave,
          despues=meta | {"archivo": archivo, "trabajadores": len(registros), "lineas": len(lineas)})
    db.commit()
    headers = {"Content-Disposition": f"attachment; filename={archivo}", "X-Export-Estado": estado,
               "X-Export-Version": str(version), "Access-Control-Expose-Headers": "Content-Disposition, X-Export-Estado"}
    if formato == "json":
        cuerpo = meta | {"conceptos": {k: {"descripcion": d, "unidad": u, "tipo": t} for k, (d, u, t) in CONCEPTOS.items()},
                         "lineas": lineas}
        return Response(content=json.dumps(cuerpo, ensure_ascii=False, indent=2), media_type="application/json",
                        headers=headers)
    buf = StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(["layout_version", "empresa_codigo", "empresa_ruc", "periodo", "estado", "version_archivo",
                "trabajador_codigo", "doc_tipo", "doc_numero", "concepto_codigo", "concepto_tipo", "unidad", "cantidad",
                "monto"])
    for li in lineas:
        w.writerow([LAYOUT_VERSION, empresa.codigo, empresa.ruc, periodo, estado, version, li["trabajador_codigo"],
                    li["doc_tipo"], li["doc_numero"], li["concepto_codigo"], li["concepto_tipo"], li["unidad"],
                    li["cantidad"], "" if li["monto"] is None else f"{li['monto']:.2f}"])
    return Response(content=buf.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)