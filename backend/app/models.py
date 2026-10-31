"""Modelo de datos Sprint 1. El esquema lo gestiona Alembic (nunca create_all)."""
from datetime import date, datetime, time
from decimal import Decimal
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
    # Sprint 6: empresa fija del usuario (null = todas; solo admin/RRHH corporativo)
    empresa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("empresa.id"), index=True)
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
    # None = se usa el refrigerio del tipo de contrato del trabajador (Sprint 4)
    refrigerio_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
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
    monto: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))  # S/ definido por administración
    moneda: Mapped[str] = mapped_column(String(3), default="PEN", server_default="PEN")
    aprobado_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
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
    monto: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
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


class HorarioPlan(Base):
    """Plan de horario semanal versionado por trabajador. Cada cambio = nueva versión."""
    __tablename__ = "horario_plan"
    __table_args__ = (UniqueConstraint("trabajador_id", "semana_inicio", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    trabajador_id: Mapped[int] = mapped_column(ForeignKey("trabajador.id"), index=True)
    semana_inicio: Mapped[date] = mapped_column(Date, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    lunes_plantilla_id: Mapped[Optional[int]] = mapped_column(ForeignKey("turno_plantilla.id"))
    martes_plantilla_id: Mapped[Optional[int]] = mapped_column(ForeignKey("turno_plantilla.id"))
    miercoles_plantilla_id: Mapped[Optional[int]] = mapped_column(ForeignKey("turno_plantilla.id"))
    jueves_plantilla_id: Mapped[Optional[int]] = mapped_column(ForeignKey("turno_plantilla.id"))
    viernes_plantilla_id: Mapped[Optional[int]] = mapped_column(ForeignKey("turno_plantilla.id"))
    sabado_plantilla_id: Mapped[Optional[int]] = mapped_column(ForeignKey("turno_plantilla.id"))
    domingo_plantilla_id: Mapped[Optional[int]] = mapped_column(ForeignKey("turno_plantilla.id"))
    alertas: Mapped[Optional[dict]] = mapped_column(JSONT)
    creado_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Marca(Base):
    """Check-in/out con validación GPS y QR. Server time autoritativo."""
    __tablename__ = "marca"
    id: Mapped[int] = mapped_column(primary_key=True)
    trabajador_id: Mapped[int] = mapped_column(ForeignKey("trabajador.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(10))  # entrada|salida
    ts_servidor: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    ts_cliente: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    lat: Mapped[Optional[float]] = mapped_column(Numeric(9, 6))
    lng: Mapped[Optional[float]] = mapped_column(Numeric(9, 6))
    distancia_m: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    sede_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sede.id"))
    metodo: Mapped[str] = mapped_column(String(20))  # gps|manual
    qr_code: Mapped[Optional[str]] = mapped_column(String(100))
    razon_manual: Mapped[Optional[str]] = mapped_column(Text)
    registrado_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"))
    validacion_estado: Mapped[str] = mapped_column(String(20), default="ok")  # ok|fuera_geocerca|duplicado
    sincronizado_offline: Mapped[bool] = mapped_column(Boolean, default=False)  # Sprint 3: marca enviada desde cola offline
    # Sprint 3 / Inc 5: marcas diferidas (PWA offline). id_idempotente = UUID generado en el dispositivo.
    id_idempotente: Mapped[Optional[str]] = mapped_column(String(36), unique=True)
    diferida: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    diferencia_min: Mapped[Optional[int]] = mapped_column(Integer)  # |ts_servidor - ts_cliente| en minutos


class Asistencia(Base):
    """Cálculo diario del motor de asistencia. Periodo cerrado = inmutable."""
    __tablename__ = "asistencia"
    __table_args__ = (UniqueConstraint("trabajador_id", "dia_operativo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    trabajador_id: Mapped[int] = mapped_column(ForeignKey("trabajador.id"), index=True)
    dia_operativo: Mapped[date] = mapped_column(Date, index=True)
    periodo: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM del periodo operativo
    turno_plantilla_id: Mapped[Optional[int]] = mapped_column(ForeignKey("turno_plantilla.id"))
    entrada_marca_id: Mapped[Optional[int]] = mapped_column(ForeignKey("marca.id"))
    salida_marca_id: Mapped[Optional[int]] = mapped_column(ForeignKey("marca.id"))
    horas_programadas: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    horas_trabajadas: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    tardanza_min: Mapped[int] = mapped_column(Integer, default=0)
    horas_extra_programadas: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    horas_extra_25: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    horas_extra_35: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    horas_nocturnas: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    exceso_no_programado: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    rule_set_id: Mapped[int] = mapped_column(ForeignKey("rule_set.id"))
    periodo_cerrado: Mapped[bool] = mapped_column(Boolean, default=False)
    calculado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RegularizacionHE(Base):
    """Bandeja del jefe: exceso no programado para regularizar."""
    __tablename__ = "regularizacion_he"
    id: Mapped[int] = mapped_column(primary_key=True)
    asistencia_id: Mapped[int] = mapped_column(ForeignKey("asistencia.id"), index=True)
    trabajador_id: Mapped[int] = mapped_column(ForeignKey("trabajador.id"), index=True)
    horas_exceso: Mapped[float] = mapped_column(Numeric(5, 2))
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")  # pendiente|aprobado|rechazado
    destino: Mapped[Optional[str]] = mapped_column(String(20))  # pago|compensacion|mixto
    decision_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"))
    decision_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    observacion: Mapped[Optional[str]] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CierrePeriodo(Base):
    """Sprint 3: Cierre mensual de periodo contable con lock de recálculo."""
    __tablename__ = "cierre_periodo"
    __table_args__ = (UniqueConstraint("empresa_id", "periodo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    periodo: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM
    cerrado_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    cerrado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reabierto_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"))
    reabierto_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    razon_reapertura: Mapped[Optional[str]] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(20), default="cerrado")  # cerrado|reabierto


class FaltaJustificada(Base):
    """Sprint 3: Justificación de faltas (ausencias) registrada por jefe/rrhh."""
    __tablename__ = "falta_justificada"
    id: Mapped[int] = mapped_column(primary_key=True)
    trabajador_id: Mapped[int] = mapped_column(ForeignKey("trabajador.id"), index=True)
    dia: Mapped[date] = mapped_column(Date, index=True)
    motivo: Mapped[str] = mapped_column(String(50))  # permiso|licencia_medica|vacaciones|otro
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    adjunto_url: Mapped[Optional[str]] = mapped_column(String(500))
    # Sprint 4: flujo trabajador solicita -> jefe aprueba/rechaza. Registro directo del jefe = aprobada.
    estado: Mapped[str] = mapped_column(String(20), default="aprobada", server_default="aprobada")  # pendiente|aprobada|rechazada
    solicitado_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"))
    justificado_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"))  # quien decide
    decidido_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    comentario_decision: Mapped[Optional[str]] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BancoHorasCompensatorias(Base):
    """Sprint 3: Banco de horas compensatorias por trabajador."""
    __tablename__ = "banco_horas_compensatorias"
    id: Mapped[int] = mapped_column(primary_key=True)
    trabajador_id: Mapped[int] = mapped_column(ForeignKey("trabajador.id"), index=True)
    fecha_movimiento: Mapped[date] = mapped_column(Date, index=True)
    tipo: Mapped[str] = mapped_column(String(20))  # credito|debito
    horas: Mapped[float] = mapped_column(Numeric(5, 2))
    saldo_anterior: Mapped[float] = mapped_column(Numeric(6, 2))
    saldo_nuevo: Mapped[float] = mapped_column(Numeric(6, 2))
    origen: Mapped[str] = mapped_column(String(100))  # HE compensatoria aprobada / Descanso tomado / Expiración
    regularizacion_id: Mapped[Optional[int]] = mapped_column(ForeignKey("regularizacion_he.id"))
    asistencia_id: Mapped[Optional[int]] = mapped_column(ForeignKey("asistencia.id"))
    dias_expiracion: Mapped[Optional[int]] = mapped_column(Integer)  # Días configurables para expirar
    fecha_expira: Mapped[Optional[date]] = mapped_column(Date)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HEProgramada(Base):
    """Sprint 4: horas extra preautorizadas por el jefe para un día operativo.

    Regla: sólo las HE programadas se pagan automáticamente (25%/35%); el exceso no programado
    va a la bandeja del jefe como no autorizado. Una fila vigente por trabajador y día (upsert).
    """
    __tablename__ = "he_programada"
    __table_args__ = (UniqueConstraint("trabajador_id", "dia"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    trabajador_id: Mapped[int] = mapped_column(ForeignKey("trabajador.id"), index=True)
    dia: Mapped[date] = mapped_column(Date, index=True)  # día operativo
    horas: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    motivo: Mapped[Optional[str]] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(20), default="vigente", server_default="vigente")  # vigente|anulada
    creado_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class HorarioAsignacion(Base):
    """Sprint 4: horario asignado al trabajador con vigencia.

    `patron` es una lista de semanas; cada semana, 7 ids de turno_plantilla (lunes..domingo, null = descanso).
    Con varias semanas el patrón rota desde la semana de `vigente_desde`. Un HorarioPlan semanal explícito
    tiene prioridad sobre la asignación (excepción puntual de esa semana).
    """
    __tablename__ = "horario_asignacion"
    id: Mapped[int] = mapped_column(primary_key=True)
    trabajador_id: Mapped[int] = mapped_column(ForeignKey("trabajador.id"), index=True)
    vigente_desde: Mapped[date] = mapped_column(Date, index=True)
    vigente_hasta: Mapped[Optional[date]] = mapped_column(Date)
    patron: Mapped[list] = mapped_column(JSONT)
    nota: Mapped[Optional[str]] = mapped_column(Text)
    creado_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
