"""Sprint 5: tramos de HE y ventana nocturna configurables (validación, preview, motor)."""
import pytest

from app.engine import calcular_horas_extra


def _cfg(t1=2, p1=25, p2=35, ini="22:00", fin="06:00"):
    return {"horas_extra": {"sobretasas": [{"hasta_horas": t1, "pct": p1}, {"hasta_horas": None, "pct": p2}]},
            "nocturno": {"inicio": ini, "fin": fin}}


def _preview(client, H, ids, cfg):
    return client.post("/rule-sets/preview", headers=H["admin"], json={
        "empresa_id": ids["emp"]["GCBSA"], "valid_from": "2029-01-01", "motivo": "tramos", "config": cfg})


def test_preview_tramos_y_ventana(client, H, ids):
    r = _preview(client, H, ids, _cfg(t1=1.5, p1=30, ini="21:00", fin="05:00"))
    assert r.status_code == 200, r.text
    rutas = {d["ruta"] for d in r.json()["diff"]}
    assert {"horas_extra.sobretasas", "nocturno.inicio", "nocturno.fin"} <= rutas


@pytest.mark.parametrize("cfg,campo", [
    (_cfg(p1=20), "horas_extra"), (_cfg(p2=30), "horas_extra"), (_cfg(p1=40, p2=35), "horas_extra"),
    (_cfg(t1=0), "horas_extra.sobretasas.0.hasta_horas"), (_cfg(t1=13), "horas_extra.sobretasas.0.hasta_horas"),
    (_cfg(ini="25:00"), "nocturno.inicio"), (_cfg(fin="6"), "nocturno.fin"), (_cfg(ini="22:00", fin="22:00"), "nocturno"),
])
def test_validaciones(client, H, ids, cfg, campo):
    r = _preview(client, H, ids, cfg)
    assert r.status_code == 422
    assert campo in {e["campo"] for e in r.json()["detail"]["errores"]}


def test_tramo_unico_rechazado(client, H, ids):
    cfg = {"horas_extra": {"sobretasas": [{"hasta_horas": None, "pct": 35}]}}
    assert _preview(client, H, ids, cfg).status_code == 422


@pytest.mark.parametrize("tope,esperado", [(2, (2.0, 1.0)), (1, (1.0, 2.0)), (3.5, (3.0, 0.0))])
def test_motor_respeta_tope_del_primer_tramo(tope, esperado):
    tramos = [{"hasta_horas": tope, "pct": 25}, {"hasta_horas": None, "pct": 35}]
    assert calcular_horas_extra(11, 8, 3, tramos) == esperado
