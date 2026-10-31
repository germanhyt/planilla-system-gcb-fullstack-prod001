"""Sprint 3: vistas 'Mis marcas' y 'Marcas por trabajador/fecha' + regresión del 422 de 'Marcar con GPS'."""
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from zoneinfo import ZoneInfo

from app.models import Marca, Sede, Trabajador, Unidad

LIMA = ZoneInfo("America/Lima")
CAMPOS = {"id", "trabajador_id", "tipo", "ts_servidor", "ts_lima", "hora_lima", "origen", "geocerca", "dia_operativo", "corte"}


@pytest.fixture
def demo(db):
    """Trabajador demo (CAV-007, vinculado a trabajador@demo.gcb.pe) con marcas controladas en una fecha fija."""
    t = db.scalar(select(Trabajador).where(Trabajador.codigo == "CAV-007"))
    sede = db.get(Sede, t.sede_id)
    base = datetime(2026, 3, 10, tzinfo=LIMA)
    datos = [("entrada", base.replace(hour=19), "gps", None, "ok", sede.lat),
             ("salida", (base + timedelta(days=1)).replace(hour=3, minute=15), "qr", "SEDE-QR", "fuera_geocerca", float(sede.lat) + 0.01)]
    for tipo, ts, metodo, qr, val, lat in datos:
        if not db.scalar(select(Marca).where(Marca.trabajador_id == t.id, Marca.ts_servidor == ts)):
            db.add(Marca(trabajador_id=t.id, tipo=tipo, ts_servidor=ts, lat=lat, lng=sede.lng, sede_id=sede.id, metodo=metodo,
                         qr_code=qr, validacion_estado=val))
    db.commit()
    return t


def test_mis_marcas_campos_y_dia_operativo(client, H, demo):
    r = client.get("/marcas/mias?desde=2026-03-10&hasta=2026-03-10", headers=H["trabajador"])
    assert r.status_code == 200, r.text
    marcas = r.json()
    assert len(marcas) == 2
    assert CAMPOS <= set(marcas[0])
    sal = next(m for m in marcas if m["tipo"] == "salida")
    ent = next(m for m in marcas if m["tipo"] == "entrada")
    # 03:15 del 11/03 pertenece al día operativo 10/03 (CAVAS corte 06:00)
    assert sal["fecha_lima"] == "2026-03-11" and sal["hora_lima"] == "03:15:00"
    assert sal["dia_operativo"] == "2026-03-10" and sal["corte"] == "06:00"
    assert sal["ts_lima"].endswith("-05:00")
    assert sal["origen"] == "qr" and sal["geocerca"] == "fuera"
    assert ent["origen"] == "gps" and ent["geocerca"] == "dentro" and ent["hora_lima"] == "19:00:00"
    # el día 11 no incluye la salida de madrugada
    r2 = client.get("/marcas/mias?desde=2026-03-11&hasta=2026-03-11", headers=H["trabajador"])
    assert all(m["id"] != sal["id"] for m in r2.json())


def test_mis_marcas_sin_vinculo_y_validaciones(client, H):
    assert client.get("/marcas/mias", headers=H["rrhh"]).status_code == 404
    assert client.get("/marcas/mias").status_code == 401
    assert client.get("/marcas/mias?desde=2026-03-10&hasta=2026-03-01", headers=H["trabajador"]).status_code == 422
    assert client.get("/marcas/mias?desde=10-03-2026", headers=H["trabajador"]).status_code == 422
    assert client.get("/marcas/mias?desde=2026-01-01&hasta=2026-12-31", headers=H["trabajador"]).status_code == 422


def test_marcas_trabajador_no_accede_listado(client, H):
    assert client.get("/marcas/", headers=H["trabajador"]).status_code == 403


def test_marcas_jefe_solo_su_unidad(client, H, db, demo):
    q = "/marcas/?desde=2026-03-10&hasta=2026-03-10"
    r = client.get(q, headers=H["jefe"])
    assert r.status_code == 200
    assert {m["unidad_id"] for m in r.json()} == {demo.unidad_id}
    assert any(m["trabajador_id"] == demo.id for m in r.json())
    # jefe de parking no ve a CAV-007
    assert client.get(q, headers=H["jefe_parking"]).json() == []
    assert client.get(f"{q}&trabajador_id={demo.id}", headers=H["jefe_parking"]).status_code == 403
    assert client.get(f"{q}&unidad_id={demo.unidad_id}", headers=H["jefe_parking"]).status_code == 403
    assert client.get(f"{q}&trabajador_id=99999999", headers=H["jefe"]).status_code == 404


@pytest.mark.parametrize("rol", ["rrhh", "admin"])
def test_marcas_rrhh_admin_ven_todo(client, H, db, demo, rol):
    park = db.scalar(select(Unidad).where(Unidad.codigo == "PARK"))
    q = "/marcas/?desde=2026-03-10&hasta=2026-03-10"
    r = client.get(f"{q}&trabajador_id={demo.id}", headers=H[rol])
    assert r.status_code == 200 and len(r.json()) == 2
    assert client.get(f"{q}&unidad_id={park.id}", headers=H[rol]).status_code == 200


def test_marcar_gps_payload_regresion_422(client, H):
    """Regresión: 'Marcar con GPS' respondía 422 porque el front enviaba el JSON doble-codificado (string JSON)."""
    payload = {"tipo": "entrada", "lat": -9.527, "lng": -77.528, "ts_cliente": datetime.now(LIMA).isoformat()}
    # Bug: el cuerpo era un string JSON (json.dumps aplicado dos veces) → la API lo rechaza con 422
    mal = client.post("/marcas/", content=json.dumps(json.dumps(payload)), headers={**H["trabajador"], "Content-Type": "application/json"})
    assert mal.status_code == 422
    # Fix: el front envía el objeto y api() lo serializa una sola vez
    ok = client.post("/marcas/", content=json.dumps(payload), headers={**H["trabajador"], "Content-Type": "application/json"})
    assert ok.status_code in (200, 400), ok.text  # 400 = duplicado en ventana de 5 min, nunca 422
    if ok.status_code == 200:
        assert ok.json()["validacion_estado"] == "ok"
        mias = client.get("/marcas/mias", headers=H["trabajador"]).json()
        m = next(x for x in mias if x["id"] == ok.json()["id"])
        assert m["origen"] == "gps" and m["geocerca"] == "dentro"


def test_marcar_qr_queda_con_origen_qr(client, H):
    r = client.post("/marcas/", json={"tipo": "salida", "qr_code": "SEDE-SISA-FICT"}, headers=H["trabajador"])
    assert r.status_code in (200, 400), r.text
    if r.status_code == 200:
        m = next(x for x in client.get("/marcas/mias", headers=H["trabajador"]).json() if x["id"] == r.json()["id"])
        assert m["origen"] == "qr" and m["geocerca"] == "sin_gps"
