"""Reglas de negocio R5/R8/R9 a nivel API (antes en test_engine_golden_r1_r9.py).

R5 usa fechas propias en 2025-06 (no el periodo abierto 2026-10 ni rule_set_id fijo) para no
chocar con el seed (asistencia única por trabajador/día) ni depender del orden de ejecución.
"""
from datetime import date

import pytest

from app.models import Asistencia, RegularizacionHE, RuleSet, Trabajador


def _regularizacion(db, codigo: str, dia: date, exceso: float) -> tuple[Asistencia, RegularizacionHE]:
    t = db.query(Trabajador).filter(Trabajador.codigo == codigo).one()
    rs = db.query(RuleSet).filter(RuleSet.empresa_id == t.empresa_id).order_by(RuleSet.valid_from).first()
    a = Asistencia(trabajador_id=t.id, dia_operativo=dia, periodo=dia.strftime("%Y-%m"), horas_programadas=8.0,
                   horas_trabajadas=8.0 + exceso, exceso_no_programado=exceso, rule_set_id=rs.id,
                   periodo_cerrado=False)
    db.add(a)
    db.flush()
    r = RegularizacionHE(asistencia_id=a.id, trabajador_id=t.id, horas_exceso=exceso, estado="pendiente")
    db.add(r)
    db.commit()
    return a, r


def test_r5_destino_pago_reparte_25_35(client, H, db):
    a, r = _regularizacion(db, "CAV-001", date(2025, 6, 10), 4.0)
    resp = client.post(f"/regularizaciones/{r.id}/decidir", json={"aprobar": True, "destino": "pago"}, headers=H["admin"])
    assert resp.status_code == 200
    db.expire_all()
    a = db.get(Asistencia, a.id)
    assert (float(a.horas_extra_25), float(a.horas_extra_35), float(a.exceso_no_programado)) == (2.0, 2.0, 0.0)


def test_r5_destino_compensacion_crea_credito(client, H, db):
    t = db.query(Trabajador).filter(Trabajador.codigo == "CAV-001").one()
    antes = client.get(f"/banco-horas/saldo/{t.id}", headers=H["admin"]).json()["saldo_horas"]
    _, r = _regularizacion(db, "CAV-001", date(2025, 6, 11), 3.0)
    resp = client.post(f"/regularizaciones/{r.id}/decidir", json={"aprobar": True, "destino": "compensacion"},
                       headers=H["admin"])
    assert resp.status_code == 200
    despues = client.get(f"/banco-horas/saldo/{t.id}", headers=H["admin"]).json()["saldo_horas"]
    assert despues == pytest.approx(antes + 3.0)


def test_r8_trabajador_no_ve_reportes(client, H):
    assert client.get("/reportes/consolidado-mensual?periodo=2025-06", headers=H["trabajador"]).status_code == 403


def test_r8_jefe_no_ve_trabajador_inexistente_ni_ajeno(client, H):
    assert client.get("/banco-horas/saldo/999999", headers=H["jefe"]).status_code in (403, 404)


def test_r9_seed_anonimizado(ids):
    assert {"CAVAS", "GCBSA"} <= set(ids["emp"])
    assert {"FT", "PT85", "PT102"} <= set(ids["tc"])