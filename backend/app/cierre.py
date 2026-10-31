"""Sprint 3 / Incremento 4: bloqueo por periodo cerrado y checklist previo al cierre.

Periodo = mes calendario YYYY-MM del *día operativo* (un turno que inicia el 31 a las 22:00 cuenta en ese mes).
Un periodo cerrado (cierre_periodo.estado = 'cerrado') bloquea marcas, regularizaciones y bonos con 409.
"""
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from .models import Asistencia, BonoNocturno, CierrePeriodo, Marca, RegularizacionHE, RuleSet, Trabajador
from .rules import efectivas

LIMA = ZoneInfo("America/Lima")


def rango(periodo: str) -> tuple[date, date]:
    anio, mes = map(int, periodo.split("-"))
    fin = date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)
    return date(anio, mes, 1), fin - timedelta(days=1)


def corte_empresa(db: Session, empresa_id: int, dia: date) -> str:
    rs = db.query(RuleSet).filter(RuleSet.empresa_id == empresa_id, RuleSet.valid_from <= dia) \
        .order_by(RuleSet.valid_from.desc()).first()
    try:
        return (efectivas(rs.config or {})["dia_operativo"].get("corte") or "00:00") if rs else "00:00"
    except Exception:  # noqa: BLE001 - config inválida: día calendario
        return "00:00"


def dia_operativo(db: Session, empresa_id: int, ts: datetime) -> date:
    """Día operativo (fecha Lima) de un instante, según el corte del rule_set vigente de la empresa."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=LIMA)
    lima = ts.astimezone(LIMA)
    hh, mm = map(int, corte_empresa(db, empresa_id, lima.date()).split(":")[:2])
    return lima.date() - timedelta(days=1) if lima.time() < time(hh, mm) else lima.date()


def esta_cerrado(db: Session, empresa_id: int, periodo: str) -> bool:
    return db.query(CierrePeriodo.id).filter(CierrePeriodo.empresa_id == empresa_id, CierrePeriodo.periodo == periodo,
                                             CierrePeriodo.estado == "cerrado").first() is not None


def exigir_abierto(db: Session, empresa_id: Optional[int], periodo: str) -> None:
    """409 si el periodo de la empresa está cerrado."""
    if empresa_id is not None and esta_cerrado(db, empresa_id, periodo):
        raise HTTPException(409, f"Periodo {periodo} cerrado: no se permiten cambios (solicite reapertura a admin)")


def exigir_abierto_trabajador(db: Session, trabajador_id: int, periodo: str) -> None:
    t = db.get(Trabajador, trabajador_id)
    exigir_abierto(db, t.empresa_id if t else None, periodo)


def exigir_abierto_ts(db: Session, trabajador: Trabajador, ts: datetime) -> None:
    exigir_abierto(db, trabajador.empresa_id, dia_operativo(db, trabajador.empresa_id, ts).strftime("%Y-%m"))


def checklist(db: Session, empresa_id: int, periodo: str) -> dict:
    """Pendientes antes de cerrar: HE sin decidir, excepciones por revisar, marcas impares, bonos sin aprobar."""
    desde, hasta = rango(periodo)
    trabs = {t.id: t for t in db.query(Trabajador).filter(Trabajador.empresa_id == empresa_id)}
    tids = list(trabs) or [-1]

    def _t(tid):
        t = trabs[tid]
        return {"trabajador_id": t.id, "codigo": t.codigo, "trabajador": f"{t.nombres} {t.apellidos}"}

    he = [_t(r.trabajador_id) | {"ref_id": r.id, "dia": a.dia_operativo.isoformat(), "horas": float(r.horas_exceso)}
          for r, a in db.query(RegularizacionHE, Asistencia).join(Asistencia, Asistencia.id == RegularizacionHE.asistencia_id)
          .filter(RegularizacionHE.estado == "pendiente", RegularizacionHE.trabajador_id.in_(tids),
                  Asistencia.dia_operativo >= desde, Asistencia.dia_operativo <= hasta).order_by(Asistencia.dia_operativo)]

    ini = datetime.combine(desde, time(0), LIMA)
    fin = datetime.combine(hasta + timedelta(days=2), time(0), LIMA)
    marcas = db.query(Marca).filter(Marca.trabajador_id.in_(tids), Marca.ts_servidor >= ini, Marca.ts_servidor < fin) \
        .order_by(Marca.ts_servidor).all()
    cortes: dict = {}
    por_dia: dict[tuple[int, date], list[str]] = {}
    geo = []
    for m in marcas:
        lima = m.ts_servidor.astimezone(LIMA)
        if lima.date() not in cortes:
            cortes[lima.date()] = corte_empresa(db, empresa_id, lima.date())
        hh, mm = map(int, cortes[lima.date()].split(":")[:2])
        d = lima.date() - timedelta(days=1) if lima.time() < time(hh, mm) else lima.date()
        if not (desde <= d <= hasta):
            continue
        por_dia.setdefault((m.trabajador_id, d), []).append(m.tipo)
        if m.validacion_estado == "fuera_geocerca":
            geo.append(_t(m.trabajador_id) | {"ref_id": m.id, "dia": d.isoformat(), "detalle": f"Marca de {m.tipo} fuera de geocerca"})
    impares = []
    for (tid, d), tipos in sorted(por_dia.items(), key=lambda x: (x[0][1], x[0][0])):
        ent, sal = tipos.count("entrada"), tipos.count("salida")
        if ent != sal:
            impares.append(_t(tid) | {"dia": d.isoformat(), "entradas": ent, "salidas": sal,
                                      "detalle": "Falta salida" if ent > sal else "Falta entrada"})
    bonos = [_t(b.trabajador_id) | {"ref_id": b.id, "cantidad": b.cantidad,
                                    "monto": float(b.monto) if b.monto is not None else None}
             for b in db.query(BonoNocturno).filter(BonoNocturno.periodo == periodo, BonoNocturno.estado == "registrado",
                                                    BonoNocturno.trabajador_id.in_(tids)).order_by(BonoNocturno.id)]
    items = {"he_sin_decidir": he, "excepciones_pendientes": geo, "marcas_incompletas": impares,
             "bonos_sin_aprobar": bonos}
    return {"empresa_id": empresa_id, "periodo": periodo, "desde": desde.isoformat(), "hasta": hasta.isoformat(),
            "cerrado": esta_cerrado(db, empresa_id, periodo),
            "conteos": {k: len(v) for k, v in items.items()}, "total_pendientes": sum(len(v) for v in items.values()),
            **items}