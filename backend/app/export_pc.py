"""Sprint 7: generacion versionada del archivo de interfaz Planilla Core (contrato PC-ASIS-1.2).

Contrato: docs/contratos/PC-ASIS-1.2.md + app/contracts/pc_asis_1_2.schema.json (generado de `ExportPC`).
- checksum = sha256 del JSON canonico de negocio (layout, empresa, periodo, estado, lineas); no incluye version ni
  fecha de generacion -> re-exportar sin cambios devuelve la MISMA version (idempotente).
- Si cambia el contenido (recalculo, cierre PRELIMINAR->FINAL, bonos...) se crea la version siguiente.
- 1.2 (S7, PO pt57u): sube la version por los conceptos BHCRE/BHDEB; 1.1 queda como historial
  (docs/contratos/PC-ASIS-1.1.md, app/contracts/pc_asis_1_1.schema.json). El checksum incluye layout_version,
  asi que el primer export 1.2 de un periodo ya exportado en 1.1 es una version nueva.
- Antes de guardar se valida contra el contrato; si no cumple, no se persiste nada.
"""
import csv
import hashlib
import json
from datetime import datetime, timezone
from io import StringIO
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .audit import audit
from .models import Auditoria, Empresa, ExportPlanilla

LAYOUT_VERSION = "PC-ASIS-1.2"
CODIGOS = Literal["HN", "TAR", "HE25", "HE35", "HNOC", "RNOC", "B3AM", "BHCRE", "BHDEB", "BHSAL"]
CSV_CABECERA = ["layout_version", "empresa_codigo", "empresa_ruc", "periodo", "estado", "version_archivo",
                "trabajador_codigo", "doc_tipo", "doc_numero", "concepto_codigo", "concepto_tipo", "unidad", "cantidad",
                "monto"]


class ConceptoPC(BaseModel):
    model_config = ConfigDict(extra="forbid")
    descripcion: str
    unidad: Literal["HORAS", "MINUTOS", "CANTIDAD"]
    tipo: Literal["INFORMATIVO", "DESCUENTO", "REMUNERATIVO", "INGRESO_INTERNO"]


class LineaPC(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trabajador_codigo: str = Field(min_length=1)
    doc_tipo: Optional[str] = None
    doc_numero: Optional[str] = None
    trabajador_nombre: str
    concepto_codigo: CODIGOS
    concepto_tipo: Literal["INFORMATIVO", "DESCUENTO", "REMUNERATIVO", "INGRESO_INTERNO"]
    unidad: Literal["HORAS", "MINUTOS", "CANTIDAD"]
    cantidad: float
    monto: Optional[float] = Field(default=None, ge=0)


class ExportPC(BaseModel):
    """Contrato del archivo JSON PC-ASIS-1.2 (el CSV lleva las mismas lineas, una fila por linea)."""
    model_config = ConfigDict(extra="forbid", title="PC-ASIS-1.2")
    layout_version: Literal["PC-ASIS-1.2"]
    empresa_codigo: str = Field(min_length=1)
    empresa_ruc: Optional[str] = None
    periodo: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    estado: Literal["PRELIMINAR", "FINAL"]
    version_archivo: int = Field(ge=1)
    generado_en: str
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    conceptos: dict[CODIGOS, ConceptoPC]
    lineas: list[LineaPC]


def json_schema() -> dict:
    return ExportPC.model_json_schema()


def checksum(meta: dict, lineas: list[dict]) -> str:
    canon = {k: meta[k] for k in ("layout_version", "empresa_codigo", "empresa_ruc", "periodo", "estado")}
    canon["lineas"] = lineas
    return hashlib.sha256(json.dumps(canon, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def _csv(doc: dict) -> str:
    buf = StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(CSV_CABECERA)
    for li in doc["lineas"]:
        w.writerow([doc["layout_version"], doc["empresa_codigo"], doc["empresa_ruc"], doc["periodo"], doc["estado"],
                    doc["version_archivo"], li["trabajador_codigo"], li["doc_tipo"], li["doc_numero"],
                    li["concepto_codigo"], li["concepto_tipo"], li["unidad"], li["cantidad"],
                    "" if li["monto"] is None else f"{li['monto']:.2f}"])
    return buf.getvalue()


def ultima(db: Session, empresa_id: int, periodo: str, formato: str) -> Optional[ExportPlanilla]:
    return db.query(ExportPlanilla).filter(ExportPlanilla.empresa_id == empresa_id, ExportPlanilla.periodo == periodo,
                                           ExportPlanilla.formato == formato) \
        .order_by(ExportPlanilla.version.desc()).first()


def generar_export(db: Session, empresa: Empresa, periodo: str, formato: str,
                   user_id: Optional[int]) -> tuple[ExportPlanilla, bool]:
    """Genera (o reutiliza) la version del archivo. Devuelve (fila, reutilizada). Hace commit."""
    from .routers.reportes import _consolidado_mensual_data, _lineas, conceptos, periodo_cerrado, rango
    estado = "FINAL" if periodo_cerrado(db, empresa.id, periodo) else "PRELIMINAR"
    registros = _consolidado_mensual_data(db, periodo, empresa.id, None, None)
    lineas = _lineas(registros)
    meta = {"layout_version": LAYOUT_VERSION, "empresa_codigo": empresa.codigo, "empresa_ruc": empresa.ruc,
            "periodo": periodo, "estado": estado}
    suma = checksum(meta, lineas)
    prev = ultima(db, empresa.id, periodo, formato)
    if prev and prev.checksum == suma:
        audit(db, user_id, "reexportar_sin_cambios", "export_planilla", prev.id,
              despues={"archivo": prev.archivo, "version": prev.version, "checksum": suma})
        db.commit()
        return prev, True
    # Continuidad con versiones numeradas antes de S7 (solo auditoria).
    legado = db.scalar(select(func.count(Auditoria.id)).where(
        Auditoria.entidad == "export_planilla_core", Auditoria.entidad_id == f"{empresa.codigo}:{periodo}")) or 0
    # La numeracion es por empresa+periodo (comun a csv/json); la reutilizacion es por formato.
    maxv = db.scalar(select(func.max(ExportPlanilla.version)).where(ExportPlanilla.empresa_id == empresa.id,
                                                                     ExportPlanilla.periodo == periodo)) or 0
    version = max(maxv, legado) + 1
    _, hasta = rango(periodo)
    doc = meta | {"version_archivo": version,
                  "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"), "checksum": suma,
                  "conceptos": conceptos(db, empresa.id, hasta), "lineas": lineas}
    ExportPC.model_validate(doc)  # contrato: falla -> no se persiste
    archivo = f"PC_{empresa.codigo}_{periodo.replace('-', '')}_v{version}_{estado}.{formato}"
    contenido = json.dumps(doc, ensure_ascii=False, indent=2) if formato == "json" else _csv(doc)
    row = ExportPlanilla(empresa_id=empresa.id, periodo=periodo, formato=formato, version=version, estado=estado,
                         layout_version=LAYOUT_VERSION, checksum=suma, archivo=archivo, contenido=contenido,
                         trabajadores=len(registros), lineas=len(lineas), generado_por=user_id)
    db.add(row)
    db.flush()
    # Entidad/clave compatibles con la auditoria pre-S7 (export_planilla_core, "EMP:AAAA-MM").
    audit(db, user_id, "exportar", "export_planilla_core", f"{empresa.codigo}:{periodo}",
          despues={"export_id": row.id, "archivo": archivo, "version": version, "estado": estado, "checksum": suma,
                   "trabajadores": len(registros), "lineas": len(lineas), "periodo": periodo,
                   "empresa_codigo": empresa.codigo})
    db.commit()
    return row, False


def out(e: ExportPlanilla) -> dict:
    return {"id": e.id, "empresa_id": e.empresa_id, "periodo": e.periodo, "formato": e.formato, "version": e.version,
            "estado": e.estado, "layout_version": e.layout_version, "checksum": e.checksum, "archivo": e.archivo,
            "trabajadores": e.trabajadores, "lineas": e.lineas, "generado_por": e.generado_por,
            "generado_en": e.generado_en.isoformat() if e.generado_en else None}
