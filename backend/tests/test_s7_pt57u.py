"""PO pt57u: rule_set GCB SA v2 (inmutabilidad), conciliacion del banco en re-cierre, alertas diarias, layout 1.2."""
import importlib.util
import os
from datetime import date, datetime

import pytest
from sqlalchemy import select
from zoneinfo import ZoneInfo

from app import alertas
from app.engine import recalcular_trabajador_periodo
from app.export_pc import LAYOUT_VERSION
from app.models import (
    Auditoria,
    BancoHorasCompensatorias,
    BonoNocturno,
    Empresa,
    HEProgramada,
    Notificacion,
    RuleSet,
    Trabajo,
    Usuario,
)
from app.rules import GCB_SA, GCB_SA_V2, GCB_SA_V2_DESDE, GCB_SA_V2_MOTIVO, efectivas
from tests.test_engine_golden_gcbsa import LUNES, lima
from tests.test_engine_golden_gcbsa import gcb as gcb  # noqa: F401
from tests.test_s6_po_decisiones import con_v2

LIMA = ZoneInfo("America/Lima")
MIG = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions", "20261101_9d2e4f6a8b10_gcbsa_rule_set_v2.py")


def _mig():
    spec = importlib.util.spec_from_file_location("mig_v2", MIG)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _empresa(db, uid, cfg):
    e = Empresa(codigo=f"M{uid}", razon_social=f"GCB v2 {uid}", ruc=f"23{uid[1:]}999")
    db.add(e)
    db.flush()
    rs = RuleSet(empresa_id=e.id, version=1, valid_from=date(2026, 1, 1), config=cfg)
    db.add(rs)
    db.commit()
    return e, rs


# ---------- 1) rule_set versionado
def test_v1_restaurada_y_v2_separada():
    assert "destino_programadas" not in GCB_SA["horas_extra"]
    assert efectivas(GCB_SA)["horas_extra"]["destino_programadas"] == "pago"
    assert efectivas(GCB_SA_V2)["horas_extra"]["destino_programadas"] == "compensacion"
    assert GCB_SA_V2_DESDE == date(2026, 11, 1)


def test_migracion_restaura_y_publica_v2_idempotente_auditada(db, unique_id):
    m = _mig()
    assert m.MOTIVO == GCB_SA_V2_MOTIVO and m.DESDE == GCB_SA_V2_DESDE
    e, v1 = _empresa(db, unique_id, GCB_SA_V2)  # simula la modificacion in situ de S6
    r = m.aplicar(db.connection(), e.codigo)
    assert r["restauradas"] == [v1.id] and r["creada"]
    assert m.aplicar(db.connection(), e.codigo) == {"restauradas": [], "creada": None}  # re-ejecutable
    db.commit()
    db.expire_all()
    rss = db.scalars(select(RuleSet).where(RuleSet.empresa_id == e.id).order_by(RuleSet.version)).all()
    assert [(x.version, x.valid_from) for x in rss] == [(1, date(2026, 1, 1)), (2, GCB_SA_V2_DESDE)]
    assert "destino_programadas" not in rss[0].config["horas_extra"]
    assert rss[1].config["horas_extra"]["destino_programadas"] == "compensacion" and rss[1].motivo == m.MOTIVO
    au = db.scalars(select(Auditoria).where(Auditoria.entidad == "rule_set",
                                            Auditoria.entidad_id.in_([str(v1.id), str(r["creada"])]))).all()
    assert sorted(a.accion for a in au) == ["crear", "restaurar"]


def test_seed_publica_v2_una_vez(db, unique_id):
    from seed import publicar_gcb_v2
    e, v1 = _empresa(db, unique_id, GCB_SA)
    rs = publicar_gcb_v2(db, e.id)
    assert rs and rs.version == 2 and rs.config["horas_extra"]["destino_programadas"] == "compensacion"
    assert publicar_gcb_v2(db, e.id) is None
    db.commit()
    assert db.scalar(select(Auditoria).where(Auditoria.entidad == "rule_set", Auditoria.entidad_id == str(rs.id)))


# ---------- 2) banco: re-cierre concilia por delta
def _cerrar(client, H, per):
    c = client.post("/periodos/cerrar", headers=H["admin"], json=per | {"confirmar": True})
    assert c.status_code in (200, 201), c.text
    return c.json()["id"]


def _reabrir(client, H, pid):
    assert client.post(f"/periodos/reabrir/{pid}", headers=H["admin"],
                       json={"razon_reapertura": "ajuste HE programada"}).status_code == 200


def test_reapertura_recierre_ajusta_banco_por_delta(client, H, db, gcb):  # noqa: F811
    emp, trabajador, marcar = gcb
    con_v2(db, emp)
    t = trabajador("dia")
    db.add(HEProgramada(trabajador_id=t.id, dia=LUNES, horas=2.0, creado_por=db.query(Usuario).first().id))
    db.commit()
    marcar(t, lima(LUNES, 8), lima(LUNES, 18))
    assert recalcular_trabajador_periodo(db, t.id, "2025-03")
    per = {"empresa_id": emp.id, "periodo": "2025-03"}

    def movs():
        db.expire_all()
        return [(m.tipo, float(m.horas), float(m.saldo_nuevo), m.origen) for m in db.scalars(
            select(BancoHorasCompensatorias).where(BancoHorasCompensatorias.trabajador_id == t.id)
            .order_by(BancoHorasCompensatorias.id))]

    def cambiar(horas):
        db.expire_all()
        h = db.scalar(select(HEProgramada).where(HEProgramada.trabajador_id == t.id))
        h.horas = horas
        db.commit()
        recalcular_trabajador_periodo(db, t.id, "2025-03")

    pid = _cerrar(client, H, per)
    assert movs() == [("credito", 2.0, 2.0, "HE programada a compensacion")]
    _reabrir(client, H, pid)
    cambiar(1.0)
    pid = _cerrar(client, H, per)
    assert movs()[1:] == [("debito", 1.0, 1.0, "Ajuste HE programada (re-cierre)")]
    au = db.scalars(select(Auditoria).where(Auditoria.entidad == "cierre_periodo", Auditoria.entidad_id == str(pid),
                                        Auditoria.accion == "cerrar_periodo").order_by(Auditoria.id.desc())).first()
    assert au.despues["he_programadas_al_banco"]["ajustes"][0]["delta"] == -1.0
    _reabrir(client, H, pid)  # re-cierre sin cambios: nada nuevo
    pid = _cerrar(client, H, per)
    assert len(movs()) == 2
    _reabrir(client, H, pid)
    cambiar(3.0)  # programa 3 h pero solo hay 2 h de exceso -> banco 2 h -> ajuste +1
    _cerrar(client, H, per)
    assert movs()[2:] == [("credito", 1.0, 2.0, "Ajuste HE programada (re-cierre)")]


# ---------- 3) alertas diarias
@pytest.fixture
def limpio_diario(db):
    db.query(Trabajo).filter(Trabajo.tipo == alertas.TIPO_DIARIO).delete()
    db.commit()
    yield
    db.query(Trabajo).filter(Trabajo.tipo == alertas.TIPO_DIARIO).delete()
    db.commit()


def test_alertas_diarias_una_vez_por_dia_sin_duplicar(db, gcb, limpio_diario):  # noqa: F811
    emp, trabajador, _ = gcb
    t = trabajador("dia")
    db.add(BonoNocturno(trabajador_id=t.id, periodo="2027-04", cantidad=2, registrado_por=db.query(Usuario).first().id))
    db.commit()

    def avisos():
        db.expire_all()
        return db.scalars(select(Notificacion).where(Notificacion.empresa_id == emp.id,
                                                     Notificacion.tipo == "bonos_sin_aprobar")).all()

    assert alertas.evaluar_diario(db, datetime(2027, 4, 5, 6, 59, tzinfo=LIMA)) is None  # antes de las 07:00
    assert avisos() == []
    r = alertas.evaluar_diario(db, datetime(2027, 4, 5, 7, 0, tzinfo=LIMA))
    assert r is not None and "2027-04" in r[emp.codigo]
    assert len(avisos()) == 1
    assert alertas.evaluar_diario(db, datetime(2027, 4, 5, 15, 0, tzinfo=LIMA)) is None  # ya corrio hoy
    assert alertas.evaluar_diario(db, datetime(2027, 4, 6, 7, 30, tzinfo=LIMA)) is not None  # dia siguiente
    alertas.generar(db, emp.id, "2027-04")  # boton manual: tampoco duplica
    db.commit()
    assert len(avisos()) == 1
    corr = db.scalars(select(Trabajo).where(Trabajo.tipo == alertas.TIPO_DIARIO)).all()
    assert sorted(x.parametros["fecha"] for x in corr) == ["2027-04-05", "2027-04-06"]


def test_alertas_diarias_hora_utc_se_interpreta_en_lima(db, limpio_diario):
    from datetime import timezone
    # 11:59 UTC = 06:59 Lima -> no corre; 12:00 UTC = 07:00 Lima -> corre
    assert alertas.evaluar_diario(db, datetime(2027, 5, 3, 11, 59, tzinfo=timezone.utc)) is None
    assert alertas.evaluar_diario(db, datetime(2027, 5, 3, 12, 0, tzinfo=timezone.utc)) is not None


def test_periodo_anterior():
    assert alertas._periodo_anterior("2027-01") == "2026-12" and alertas._periodo_anterior("2027-04") == "2027-03"


# ---------- 4) layout
def test_layout_1_2_y_historial_1_1():
    assert LAYOUT_VERSION == "PC-ASIS-1.2"
    base = os.path.join(os.path.dirname(__file__), "..", "app", "contracts")
    assert os.path.exists(os.path.join(base, "pc_asis_1_1.schema.json"))  # historial
