"""Reglas confirmadas como configuración. BASE = lógica base; cada rule_set guarda solo overrides por empresa."""
import copy
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

BASE: dict = {
    "tolerancia": {"modo": "umbral_perdona", "minutos": 10},
    "dia_operativo": {"tipo": "calendario", "inicio": "00:00", "fin": "24:00", "corte": "00:00",
                      "turno_cuenta_dia_inicio": True},
    "periodo": {"tipo": "mes_calendario", "por": "dia_operativo"},
    "horas_extra": {"solo_preprogramadas": True, "destino_default": "pago", "destino_programadas": "pago",
                    "exceso_no_programado": "bandeja_jefe", "regularizacion_auditada": True, "pct_pago_mixto": 50,
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


HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class Sobretasa(BaseModel):
    hasta_horas: Optional[float] = Field(None, gt=0, le=12)
    pct: float = Field(ge=0, le=200)


class HorasExtra(BaseModel):
    solo_preprogramadas: bool
    destino_default: Literal["pago", "compensacion", "mixto"]
    # HE pre-programadas: pago (HE25/HE35) o compensacion (banco de horas, acreditado al cerrar el periodo). PO pt54u.
    destino_programadas: Literal["pago", "compensacion"] = "pago"
    exceso_no_programado: Literal["bandeja_jefe"]
    regularizacion_auditada: bool
    sobretasas: list[Sobretasa]
    pct_pago_mixto: float = Field(50, ge=0, le=100)  # destino mixto sin horas_pago explícitas: % a pago, resto a bolsa

    @model_validator(mode="after")
    def _tramos(self):
        # Dos tramos (HE25 / HE35): el 1.º con tope de horas, el último abierto. Mínimos legales D.S. 007-2002-TR: 25 % y 35 %.
        t = self.sobretasas
        if len(t) != 2 or t[0].hasta_horas is None or t[1].hasta_horas is not None:
            raise ValueError("sobretasas: se esperan 2 tramos; el 1.º con hasta_horas y el 2.º abierto (hasta_horas null)")
        if t[0].pct < 25 or t[1].pct < 35:
            raise ValueError("sobretasas: mínimo legal 25 % (1.er tramo) y 35 % (2.º tramo)")
        if t[1].pct < t[0].pct:
            raise ValueError("sobretasas: el 2.º tramo no puede pagar menos que el 1.º")
        return self


class PartTime(BaseModel):
    alerta_promedio_diario_horas: float
    ventana: Literal["semanal"]
    bloqueante: Literal[False]


class Nocturno(BaseModel):
    inicio: str = Field(pattern=HHMM)
    fin: str = Field(pattern=HHMM)
    siempre_calcular: Literal[True]
    mostrar_sobretasa_separada: bool

    @model_validator(mode="after")
    def _ventana(self):
        if self.inicio == self.fin:
            raise ValueError("nocturno: inicio y fin no pueden ser iguales")
        return self


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


def diff(antes: dict, despues: dict, ruta: str = "") -> list[dict]:
    """Diferencias hoja a hoja entre dos configuraciones efectivas: [{ruta, antes, despues}]."""
    out = []
    for k in sorted(set(antes) | set(despues)):
        a, d, r = antes.get(k), despues.get(k), f"{ruta}.{k}" if ruta else k
        if isinstance(a, dict) and isinstance(d, dict):
            out += diff(a, d, r)
        elif a != d:
            out.append({"ruta": r, "antes": a, "despues": d})
    return out


def efectivas(overrides: dict) -> dict:
    """Valida y devuelve BASE + overrides. Lanza ValidationError si la config es inválida."""
    return ReglasEfectivas(**deep_merge(BASE, overrides)).model_dump()


# Overrides confirmados por empresa (usados por la semilla)
# CAVAS_DEMO: versión demo/legado (valid_from 2026-01-01) para que los datos de prueba previos al piloto sigan calculando.
CAVAS_DEMO = {"dia_operativo": {"tipo": "operativo", "inicio": "08:00", "fin": "03:00", "corte": "06:00"},
         "horas_extra": {"destino_default": "pago"}, "nocturno": {"mostrar_sobretasa_separada": True}}
# Reglas reales de CAVAS aprobadas por el PO, vigentes desde CAVAS_REAL_DESDE: tolerancia umbral 10 min, corte 06:00,
# HE destino por defecto pago, sobretasa nocturna en columna aparte. (El refrigerio PT 45 min vive en tipo_contrato.)
CAVAS_REAL_DESDE = date(2026, 11, 1)
CAVAS = {"tolerancia": {"modo": "umbral_perdona", "minutos": 10},
         "dia_operativo": {"tipo": "operativo", "inicio": "08:00", "fin": "03:00", "corte": "06:00"},
         "horas_extra": {"destino_default": "pago"}, "nocturno": {"mostrar_sobretasa_separada": True}}
# GCB SA (GRUPO CORDILLERA BLANCA S.A.) - explicito aunque coincida con BASE en varios puntos (Sprint 6):
# dia calendario (corte 00:00, un turno que cruza medianoche cuenta en el dia de inicio), tolerancia 10 min
# umbral_perdona, HE por defecto a compensacion (banco de horas), nocturnas calculadas sin recargo separado.
GCB_SA = {"tolerancia": {"modo": "umbral_perdona", "minutos": 10},
          "dia_operativo": {"tipo": "calendario", "corte": "00:00", "turno_cuenta_dia_inicio": True},
          "horas_extra": {"destino_default": "compensacion", "destino_programadas": "compensacion"},
          "nocturno": {"mostrar_sobretasa_separada": False}}
