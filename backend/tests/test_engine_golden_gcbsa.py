"""Golden tests del motor para GCB SA (GRUPO CORDILLERA BLANCA S.A.), Sprint 6.

Reglas = rules.GCB_SA (hereda la base CAVAS): dia calendario (corte 00:00, el turno que cruza medianoche cuenta
en el dia de inicio), tolerancia umbral_perdona 10 min, HE no programadas a compensacion (banco de horas),
horas nocturnas calculadas pero SIN recargo nocturno separado (no hay RNOC en el export).
Cada test crea su propia empresa con fechas fijas en 2025-03.
"""
from datetime import date, datetime, time, timedelta

import pytest
from zoneinfo import ZoneInfo

from app.engine import calcular_asistencia_dia, recalcular_trabajador_periodo
from app.models import (
    Asistencia,
    BancoHorasCompensatorias,
    Empresa,
    HorarioPlan,
    Marca,
    RegularizacionHE,
    RuleSet,
    TipoContrato,
    Trabajador,
    TurnoPlantilla,
    Unidad,
    Usuario,
)
from app.rules import GCB_SA, efectivas

LIMA = ZoneInfo("America/Lima")
LUNES = date(2025, 3, 3)
REGLAS = efectivas(GCB_SA)


def lima(d: date, hh: int, mm: int = 0, dias: int = 0) -> datetime:
    return datetime.combine(d + timedelta(days=dias), time(hh, mm), tzinfo=LIMA)


def test_reglas_gcbsa_explicitas():
    assert REGLAS["dia_operativo"]["tipo"] == "calendario" and REGLAS["dia_operativo"]["corte"] == "00:00"
    assert REGLAS["tolerancia"] == {"modo": "umbral_perdona", "minutos": 10} | {
        k: v for k, v in REGLAS["tolerancia"].items() if k not in ("modo", "minutos")}
    assert REGLAS["horas_extra"]["destino_default"] == "compensacion"
    assert REGLAS["nocturno"]["mostrar_sobretasa_separada"] is False


@pytest.fixture
def gcb(db, unique_id):
    emp = Empresa(codigo=f"S{unique_id}", razon_social=f"GCB golden {unique_id}", ruc=f"21{unique_id[1:]}999")
    db.add(emp)
    db.flush()
    db.add(RuleSet(empresa_id=emp.id, version=1, valid_from=date(2020, 1, 1), config=GCB_SA))
    uni = Unidad(empresa_id=emp.id, codigo="GR", nombre="Refugio golden")
    db.add(uni)
    db.flush()
    turnos = {"dia": TurnoPlantilla(unidad_id=uni.id, nombre="08-16", inicio=time(8), fin=time(16), refrigerio_min=45),
              "cierre": TurnoPlantilla(unidad_id=uni.id, nombre="17-01", inicio=time(17), fin=time(1), refrigerio_min=45)}
    db.add_all(turnos.values())
    db.flush()
    creador = db.query(Usuario).first().id
    ft = db.query(TipoContrato).filter(TipoContrato.codigo == "FT").one().id
    n = 0

    def trabajador(turno: str = "dia") -> Trabajador:
        nonlocal n
        n += 1
        t = Trabajador(codigo=f"S{unique_id}{n}", empresa_id=emp.id, unidad_id=uni.id, doc_tipo="DNI",
                       doc_numero=f"8{unique_id[1:]}{n:02d}", nombres="Anon", apellidos=f"GCB {n}",
                       tipo_contrato_id=ft, fecha_ingreso=date(2024, 1, 1))
        db.add(t)
        db.flush()
        db.add(HorarioPlan(trabajador_id=t.id, semana_inicio=LUNES, version=1, creado_por=creador,
                           **{f"{d}_plantilla_id": turnos[turno].id for d in
                              ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")}))
        db.flush()
        return t

    def marcar(t: Trabajador, entrada: datetime, salida: datetime):
        db.add_all([Marca(trabajador_id=t.id, tipo="entrada", ts_servidor=entrada, metodo="gps", validacion_estado="ok"),
                    Marca(trabajador_id=t.id, tipo="salida", ts_servidor=salida, metodo="gps", validacion_estado="ok")])
        db.commit()

    return emp, trabajador, marcar


def test_turno_dia_jornada_exacta(db, gcb):
    _, trabajador, marcar = gcb
    t = trabajador("dia")
    marcar(t, lima(LUNES, 8), lima(LUNES, 16))
    r = calcular_asistencia_dia(db, t.id, LUNES, REGLAS)
    assert (r["dia_operativo"], r["periodo"]) == (LUNES, "2025-03")
    assert (r["horas_programadas"], r["horas_trabajadas"]) == (7.25, 7.25)
    assert (r["tardanza_min"], r["exceso_no_programado"], r["horas_nocturnas"]) == (0, 0, 0.0)


@pytest.mark.parametrize("hh,mm,tardanza", [(8, 0, 0), (8, 10, 0), (8, 11, 11), (8, 30, 30)])
def test_tardanza_umbral_10(db, gcb, hh, mm, tardanza):
    _, trabajador, marcar = gcb
    t = trabajador("dia")
    marcar(t, lima(LUNES, hh, mm), lima(LUNES, 16))
    assert calcular_asistencia_dia(db, t.id, LUNES, REGLAS)["tardanza_min"] == tardanza


def test_turno_cierre_cruza_medianoche_cuenta_en_dia_calendario_de_inicio(db, gcb):
    """17:00 -> 01:30 del dia siguiente: dia operativo = dia de entrada (corte 00:00), nocturnas 22:00-01:30."""
    _, trabajador, marcar = gcb
    t = trabajador("cierre")
    d = LUNES + timedelta(days=6)  # domingo 09/03: sale el lunes 10/03 01:30
    marcar(t, lima(d, 17), lima(d, 1, 30, dias=1))
    r = calcular_asistencia_dia(db, t.id, d, REGLAS)
    assert (r["dia_operativo"], r["periodo"]) == (d, "2025-03")
    assert r["horas_programadas"] == 7.25
    assert r["horas_trabajadas"] == 7.75
    assert r["horas_nocturnas"] == 3.5
    assert r["exceso_no_programado"] == 0.5
    assert calcular_asistencia_dia(db, t.id, d + timedelta(days=1), REGLAS) is None


def test_he_no_programada_aprobada_va_al_banco_por_defecto(client, H, db, gcb):
    emp, trabajador, marcar = gcb
    t = trabajador("dia")
    marcar(t, lima(LUNES, 8), lima(LUNES, 18))
    assert recalcular_trabajador_periodo(db, t.id, "2025-03")
    reg = db.query(RegularizacionHE).filter(RegularizacionHE.trabajador_id == t.id).one()
    assert float(reg.horas_exceso) == 2.0 and reg.estado == "pendiente"
    r = client.post(f"/regularizaciones/{reg.id}/decidir", headers=H["admin"], json={"aprobar": True})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(RegularizacionHE, reg.id).destino == "compensacion"
    cred = db.query(BancoHorasCompensatorias).filter(BancoHorasCompensatorias.trabajador_id == t.id,
                                                     BancoHorasCompensatorias.tipo == "credito").all()
    assert [float(c.horas) for c in cred] == [2.0]


def test_cierre_y_export_sin_rnoc_separado(client, H, db, gcb):
    emp, trabajador, marcar = gcb
    t = trabajador("cierre")
    marcar(t, lima(LUNES, 17), lima(LUNES, 1, dias=1))
    assert recalcular_trabajador_periodo(db, t.id, "2025-03")
    per = {"empresa_id": emp.id, "periodo": "2025-03"}
    c = client.post("/periodos/cerrar", headers=H["rrhh"], json=per | {"confirmar": True})
    assert c.status_code in (200, 201), c.text
    e = client.post("/reportes/export-planilla-core", headers=H["rrhh"], params=per | {"formato": "json"}).json()
    assert e["estado"] == "FINAL"
    conceptos = {li["concepto_codigo"] for li in e["lineas"] if li["trabajador_codigo"] == t.codigo}
    assert "HNOC" in conceptos and "RNOC" not in conceptos
    hnoc = next(li for li in e["lineas"] if li["trabajador_codigo"] == t.codigo and li["concepto_codigo"] == "HNOC")
    assert float(hnoc["cantidad"]) == 3.0
    c = client.get("/reportes/consolidado-mensual", headers=H["rrhh"], params=per).json()
    fila = next(f for f in c["registros"] if f["codigo"] == t.codigo)
    assert fila["horas_nocturnas"] == 3.0 and not fila.get("recargo_nocturno")


def test_recalculo_usa_reglas_vigentes_por_dia(db, gcb):
    """Un rule_set nuevo a mitad de mes rige desde su valid_from (antes se aplicaba el del dia 1 a todo el mes)."""
    emp, trabajador, marcar = gcb
    db.add(RuleSet(empresa_id=emp.id, version=2, valid_from=LUNES + timedelta(days=3),
                   config=GCB_SA | {"tolerancia": {"modo": "umbral_perdona", "minutos": 0}}))
    t = trabajador("dia")
    marcar(t, lima(LUNES, 8, 5), lima(LUNES, 16))
    jueves = LUNES + timedelta(days=3)
    marcar(t, lima(jueves, 8, 5), lima(jueves, 16))
    assert recalcular_trabajador_periodo(db, t.id, "2025-03")
    tard = {a.dia_operativo: a.tardanza_min for a in db.query(Asistencia).filter(Asistencia.trabajador_id == t.id)}
    assert tard == {LUNES: 0, jueves: 5}
