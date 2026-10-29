"""Modelo de datos Sprint 1. El esquema lo gestiona Alembic (nunca create_all)."""
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

JSONT = JSON().with_variant(JSONB(), "postgresql")
ROLES = ("trabajador", "jefe", "rrhh", "admin")


class Empresa(Base):
    __tablename__ = "empresa"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    razon_social: Mapped[str] = mapped_column(String(200))
    ruc: Mapped[str] = mapped_column(String(11), unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Unidad(Base):
    __tablename__ = "unidad"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"))
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Sede(Base):
    __tablename__ = "sede"
    id: Mapped[int] = mapped_column(primary_key=True)
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidad.id"))
    nombre: Mapped[str] = mapped_column(String(200))
    direccion: Mapped[Optional[str]] = mapped_column(String(300))
    lat: Mapped[float] = mapped_column(Numeric(9, 6))
    lng: Mapped[float] = mapped_column(Numeric(9, 6))
    radio_geocerca_m: Mapped[int] = mapped_column(Integer, default=100)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class TipoContrato(Base):
    """Tipos configurables: FT, PT85, PT102 (y los que se agreguen)."""
    __tablename__ = "tipo_contrato"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(100))
    horas_mes: Mapped[int] = mapped_column(Integer)
    jornada_diaria_min: Mapped[int] = mapped_column(Integer)
    es_part_time: Mapped[bool] = mapped_column(Boolean, default=False)
    refrigerio_min: Mapped[int] = mapped_column(Integer, default=45)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    rol: Mapped[str] = mapped_column(String(20))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Perfil
    nombre: Mapped[str] = mapped_column(String(200))
    telefono: Mapped[Optional[str]] = mapped_column(String(30))
    idioma: Mapped[str] = mapped_column(String(5), default="es")
    zona_horaria: Mapped[str] = mapped_column(String(50), default="America/Lima")
    # Alcance del jefe (unidad que supervisa)
    unidad_id: Mapped[Optional[int]] = mapped_column(ForeignKey("unidad.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultimo_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Trabajador(Base):
    __tablename__ = "trabajador"
    __table_args__ = (UniqueConstraint("doc_tipo", "doc_numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"))
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidad.id"))
    sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sede.id"))
    doc_tipo: Mapped[str] = mapped_column(String(10), default="DNI")
    doc_numero: Mapped[str] = mapped_column(String(20))
    nombres: Mapped[str] = mapped_column(String(100))
    apellidos: Mapped[str] = mapped_column(String(100))
    area: Mapped[Optional[str]] = mapped_column(String(100))
    cargo: Mapped[Optional[str]] = mapped_column(String(100))
    tipo_contrato_id: Mapped[int] = mapped_column(ForeignKey("tipo_contrato.id"))
    jornada_diaria_min: Mapped[Optional[int]] = mapped_column(Integer)  # override del tipo de contrato
    fecha_ingreso: Mapped[date] = mapped_column(Date)
    fecha_cese: Mapped[Optional[date]] = mapped_column(Date)
    jefe_usuario_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"))
    usuario_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"), unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class TurnoPlantilla(Base):
    """Catálogo de plantillas de turno (semilla de patrones; la programación semanal es Sprint 2)."""
    __tablename__ = "turno_plantilla"
    id: Mapped[int] = mapped_column(primary_key=True)
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidad.id"))
    nombre: Mapped[str] = mapped_column(String(50))
    inicio: Mapped[time] = mapped_column(Time)
    fin: Mapped[time] = mapped_column(Time)
    refrigerio_min: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class RuleSet(Base):
    """Reglas versionadas por empresa y vigencia. Inmutables: un cambio = nueva versión."""
    __tablename__ = "rule_set"
    __table_args__ = (UniqueConstraint("empresa_id", "valid_from"), UniqueConstraint("empresa_id", "version"))
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"))
    version: Mapped[int] = mapped_column(Integer)
    valid_from: Mapped[date] = mapped_column(Date)
    config: Mapped[dict] = mapped_column(JSONT)
    motivo: Mapped[Optional[str]] = mapped_column(Text)
    creado_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BonoNocturno(Base):
    """Concepto interno 'bono nocturno 3 AM': registrado por admin por trabajador/periodo, con aprobación."""
    __tablename__ = "bono_nocturno"
    __table_args__ = (UniqueConstraint("trabajador_id", "periodo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    trabajador_id: Mapped[int] = mapped_column(ForeignKey("trabajador.id"))
    periodo: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    cantidad: Mapped[int] = mapped_column(Integer)  # número de cierres 3 AM
    observacion: Mapped[Optional[str]] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(20), default="registrado")  # registrado|aprobado|rechazado
    registrado_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    aprobado_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BonoNocturnoHistorial(Base):
    __tablename__ = "bono_nocturno_historial"
    id: Mapped[int] = mapped_column(primary_key=True)
    bono_id: Mapped[int] = mapped_column(ForeignKey("bono_nocturno.id"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    accion: Mapped[str] = mapped_column(String(20))
    cantidad: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(20))
    comentario: Mapped[Optional[str]] = mapped_column(Text)


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"))
    accion: Mapped[str] = mapped_column(String(30))  # crear|actualizar|eliminar|login_ok|login_fallido|aprobar...
    entidad: Mapped[str] = mapped_column(String(50), index=True)
    entidad_id: Mapped[Optional[str]] = mapped_column(String(50))
    antes: Mapped[Optional[dict]] = mapped_column(JSONT)
    despues: Mapped[Optional[dict]] = mapped_column(JSONT)
    ip: Mapped[Optional[str]] = mapped_column(String(64))
