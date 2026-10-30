"""Reglas confirmadas como configuración. BASE = lógica base; cada rule_set guarda solo overrides por empresa."""
import copy
from typing import Literal, Optional

from pydantic import BaseModel, Field

BASE: dict = {
    "tolerancia": {"modo": "umbral_perdona", "minutos": 10},
    "dia_operativo": {"tipo": "calendario", "inicio": "00:00", "fin": "24:00", "corte": "00:00",
                      "turno_cuenta_dia_inicio": True},
    "periodo": {"tipo": "mes_calendario", "por": "dia_operativo"},
    "horas_extra": {"solo_preprogramadas": True, "destino_default": "pago",
                    "exceso_no_programado": "bandeja_jefe", "regularizacion_auditada": True,
                    "sobretasas": [{"hasta_horas": 2, "pct": 25}, {"hasta_horas": None, "pct": 35}]},
    "part_time": {"alerta_promedio_diario_horas": 4, "ventana": "semanal", "bloqueante": False},
    "nocturno": {"inicio": "22:00", "fin": "06:00", "siempre_calcular": True, "mostrar_sobretasa_separada": False},
    "bono_nocturno_3am": {"habilitado": True, "registra_rol": "admin", "requiere_aprobacion": True},
    "marcacion_offline": {"umbral_diferida_min": 15},
}


class Tolerancia(BaseModel):
    # umbral_perdona: si tardanza <= minutos -> 0, si no cuenta completa
    # umbral_descuenta_exceso: solo cuenta lo que excede el umbral
    # sin_tolerancia: cuenta todo minuto de tardanza
    modo: Literal["umbral_perdona", "umbral_descuenta_exceso", "sin_tolerancia"]
    minutos: int = Field(ge=0, le=120)


class DiaOperativo(BaseModel):
    tipo: Literal["operativo", "calendario"]
    inicio: str
    fin: str
    corte: str  # marcas antes de esta hora pertenecen al día anterior
    turno_cuenta_dia_inicio: bool = True


class Sobretasa(BaseModel):
    hasta_horas: Optional[float]
    pct: float


class HorasExtra(BaseModel):
    solo_preprogramadas: bool
    destino_default: Literal["pago", "compensacion", "mixto"]
    exceso_no_programado: Literal["bandeja_jefe"]
    regularizacion_auditada: bool
    sobretasas: list[Sobretasa]


class PartTime(BaseModel):
    alerta_promedio_diario_horas: float
    ventana: Literal["semanal"]
    bloqueante: Literal[False]


class Nocturno(BaseModel):
    inicio: str
    fin: str
    siempre_calcular: Literal[True]
    mostrar_sobretasa_separada: bool


class Periodo(BaseModel):
    tipo: Literal["mes_calendario"]
    por: Literal["dia_operativo"]


class Bono3AM(BaseModel):
    habilitado: bool
    registra_rol: Literal["admin"]
    requiere_aprobacion: bool


class MarcacionOffline(BaseModel):
    # marcas diferidas cuya diferencia ts_servidor - ts_dispositivo supera el umbral van a la bandeja
    umbral_diferida_min: int = Field(15, ge=0, le=1440)


class ReglasEfectivas(BaseModel):
    tolerancia: Tolerancia
    dia_operativo: DiaOperativo
    periodo: Periodo
    horas_extra: HorasExtra
    part_time: PartTime
    nocturno: Nocturno
    bono_nocturno_3am: Bono3AM
    marcacion_offline: MarcacionOffline


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def efectivas(overrides: dict) -> dict:
    """Valida y devuelve BASE + overrides. Lanza ValidationError si la config es inválida."""
    return ReglasEfectivas(**deep_merge(BASE, overrides)).model_dump()


# Overrides confirmados por empresa (usados por la semilla)
CAVAS = {"dia_operativo": {"tipo": "operativo", "inicio": "08:00", "fin": "03:00", "corte": "06:00"},
         "horas_extra": {"destino_default": "pago"}, "nocturno": {"mostrar_sobretasa_separada": True}}
GCB_SA = {"dia_operativo": {"tipo": "calendario", "turno_cuenta_dia_inicio": True},
          "horas_extra": {"destino_default": "compensacion"}}
