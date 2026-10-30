from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class EmpresaIn(BaseModel):
    codigo: str
    razon_social: str
    ruc: str = Field(pattern=r"^\d{11}$")
    activo: bool = True


class UnidadIn(BaseModel):
    empresa_id: int
    codigo: str
    nombre: str
    activo: bool = True


class SedeIn(BaseModel):
    unidad_id: int
    nombre: str
    direccion: Optional[str] = None
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    radio_geocerca_m: int = Field(100, gt=0, le=5000)
    activo: bool = True


class TipoContratoIn(BaseModel):
    codigo: str
    nombre: str
    horas_mes: int = Field(gt=0, le=300)
    jornada_diaria_min: int = Field(gt=0, le=720)
    es_part_time: bool = False
    refrigerio_min: int = Field(45, ge=0, le=120)
    activo: bool = True


class TrabajadorIn(BaseModel):
    codigo: str
    empresa_id: int
    unidad_id: int
    sede_id: Optional[int] = None
    doc_tipo: str = "DNI"
    doc_numero: str
    nombres: str
    apellidos: str
    area: Optional[str] = None
    cargo: Optional[str] = None
    tipo_contrato_id: int
    jornada_diaria_min: Optional[int] = Field(None, gt=0, le=720)
    fecha_ingreso: date
    fecha_cese: Optional[date] = None
    jefe_usuario_id: Optional[int] = None
    usuario_id: Optional[int] = None
    activo: bool = True


class TurnoPlantillaIn(BaseModel):
    unidad_id: int
    nombre: str
    inicio: time
    fin: time
    refrigerio_min: int = 0
    activo: bool = True


class LoginIn(BaseModel):
    email: EmailStr
    password: str


Rol = Literal["trabajador", "jefe", "rrhh", "admin"]


class UsuarioIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    rol: Rol
    nombre: str
    unidad_id: Optional[int] = None


class UsuarioUpd(BaseModel):
    rol: Optional[Rol] = None
    activo: Optional[bool] = None
    unidad_id: Optional[int] = None
    nombre: Optional[str] = None


class PerfilUpd(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    idioma: Optional[Literal["es", "en"]] = None
    zona_horaria: Optional[str] = None


class PasswordUpd(BaseModel):
    actual: str
    nueva: str = Field(min_length=8)


class RuleSetIn(BaseModel):
    empresa_id: int
    valid_from: date
    config: dict
    motivo: Optional[str] = None


class BonoIn(BaseModel):
    trabajador_id: int
    periodo: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    cantidad: int = Field(ge=0, le=31)
    monto: Optional[Decimal] = Field(None, ge=0, le=100000, decimal_places=2)  # S/; obligatorio para aprobar
    observacion: Optional[str] = None


class BonoDecision(BaseModel):
    aprobar: bool
    comentario: Optional[str] = None


class HorarioPlanIn(BaseModel):
    trabajador_id: int
    semana_inicio: date
    lunes_plantilla_id: Optional[int] = None
    martes_plantilla_id: Optional[int] = None
    miercoles_plantilla_id: Optional[int] = None
    jueves_plantilla_id: Optional[int] = None
    viernes_plantilla_id: Optional[int] = None
    sabado_plantilla_id: Optional[int] = None
    domingo_plantilla_id: Optional[int] = None


class MarcaIn(BaseModel):
    tipo: Literal["entrada", "salida"]
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    ts_cliente: Optional[datetime] = None
    qr_code: Optional[str] = None


class MarcaManualIn(BaseModel):
    trabajador_id: int
    tipo: Literal["entrada", "salida"]
    ts_servidor: datetime
    razon_manual: str
    sede_id: Optional[int] = None


class RegularizacionDecision(BaseModel):
    aprobar: bool
    destino: Optional[Literal["pago", "compensacion", "mixto"]] = None  # None al aprobar = destino_default del rule_set
    horas_pago: Optional[float] = None  # sólo mixto: horas a pagar (resto a banco). Default 50/50
    observacion: Optional[str] = None


class CierrePeriodoIn(BaseModel):
    """Sprint 3: Cerrar periodo mensual."""
    empresa_id: int
    periodo: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    confirmar: bool = False  # obligatorio si el checklist tiene pendientes


class ReaperturaPeriodoIn(BaseModel):
    """Sprint 3: Reabrir periodo cerrado (solo admin)."""
    razon_reapertura: str = Field(min_length=10)


class FaltaJustificadaIn(BaseModel):
    """Sprint 3: Justificar falta/ausencia."""
    trabajador_id: int
    dia: date
    motivo: Literal["permiso", "licencia_medica", "vacaciones", "otro"]
    descripcion: Optional[str] = None
    adjunto_url: Optional[str] = None


class ConsolidadoMensualParams(BaseModel):
    """Sprint 3: Parámetros para reporte consolidado mensual."""
    periodo: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    empresa_id: Optional[int] = None
    unidad_id: Optional[int] = None
    trabajador_id: Optional[int] = None
    formato: Literal["json", "excel", "csv"] = "json"
