"""Sprint 3 / Inc 5: marcas diferidas desde la cola offline de la PWA (idempotencia, diferida, periodo cerrado)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from zoneinfo import ZoneInfo

from app.models import CierrePeriodo, Marca, Trabajador, Usuario


@pytest.fixture
def trab(db):
    u = db.scalar(select(Usuario).where(Usuario.email == "trabajador@demo.gcb.pe"))
    return db.scalar(select(Trabajador).where(Trabajador.usuario_id == u.id))


def _offline(client, H, minutos_atras, tipo="entrada", idem=None, **extra):
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutos_atras)
    body = {"tipo": tipo, "lat": -9.527, "lng": -77.528, "ts_cliente": ts.isoformat(), "offline": True,
            "id_idempotente": idem or str(uuid.uuid4())} | extra
    return client.post("/marcas/", json=body, headers=H["trabajador"])


def test_idempotencia_no_duplica(client, H, db):
    idem = str(uuid.uuid4())
    r1 = _offline(client, H, 3, idem=idem)
    r2 = _offline(client, H, 3, idem=idem)
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    assert r1.json()["id"] == r2.json()["id"]
    assert r1.json()["repetida"] is False and r2.json()["repetida"] is True
    assert db.query(Marca).filter(Marca.id_idempotente == idem).count() == 1


def test_idempotencia_online_sin_offline(client, H, db, trab):
    """El front envia siempre el UUID: un reintento online tampoco duplica ni cae en el 400 de 5 min."""
    # Determinista: libera la ventana anti-duplicado de 5 min (BD de test) en vez de saltar el test.
    db.query(Marca).filter(Marca.trabajador_id == trab.id, Marca.tipo == "salida",
                           Marca.ts_servidor > datetime.now(timezone.utc) - timedelta(minutes=10)).delete()
    db.commit()
    idem = str(uuid.uuid4())
    r1 = client.post("/marcas/", json={"tipo": "salida", "qr_code": "SEDE-SISA-FICT", "id_idempotente": idem},
                     headers=H["trabajador"])
    assert r1.status_code == 200, r1.text
    r2 = client.post("/marcas/", json={"tipo": "salida", "qr_code": "SEDE-SISA-FICT", "id_idempotente": idem},
                     headers=H["trabajador"])
    assert r2.status_code == 200 and r2.json()["id"] == r1.json()["id"]


def test_idempotente_de_otro_trabajador_409(client, H):
    idem = str(uuid.uuid4())
    assert _offline(client, H, 2, idem=idem).status_code == 200
    r = client.post("/marcas/", json={"tipo": "entrada", "ts_cliente": datetime.now(timezone.utc).isoformat(),
                                      "offline": True, "id_idempotente": idem}, headers=H["jefe"])
    assert r.status_code in (403, 409)  # 403 si el jefe no tiene ficha de trabajador


def test_diferida_guarda_ambos_ts_y_diferencia(client, H, db):
    r = _offline(client, H, 40, tipo="salida")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["diferida"] is True and 39 <= j["diferencia_min"] <= 41
    m = db.get(Marca, j["id"])
    assert m.sincronizado_offline and m.ts_cliente < m.ts_servidor
    assert abs((m.ts_servidor - m.ts_cliente).total_seconds() / 60 - 40) < 1.5
    mias = client.get("/marcas/mias", headers=H["trabajador"]).json()
    assert next(x for x in mias if x["id"] == j["id"])["diferida"] is True


def test_offline_requiere_ts_cliente(client, H):
    r = client.post("/marcas/", json={"tipo": "entrada", "offline": True, "id_idempotente": str(uuid.uuid4())},
                    headers=H["trabajador"])
    assert r.status_code == 422


def test_bandeja_muestra_diferida_sobre_umbral(client, H, trab):
    # Dia Lima (no la TZ del contenedor) y rango de 2 dias: una marca de hace 60 min puede caer en el dia anterior
    hoy_d = datetime.now(ZoneInfo("America/Lima")).date()
    hoy, ayer = hoy_d.isoformat(), (hoy_d - timedelta(days=1)).isoformat()
    sobre = _offline(client, H, 60).json()["id"]  # 60 min > umbral 15
    bajo = _offline(client, H, 5, tipo="salida").json()["id"]  # 5 min <= umbral: no va a la bandeja
    items = client.get(f"/excepciones/bandeja?desde={ayer}&hasta={hoy}&tipo=marca_diferida", headers=H["rrhh"]).json()
    refs = {i["ref_id"] for i in items}
    assert sobre in refs and bajo not in refs
    assert all(i["tipo"] == "marca_diferida" and "umbral 15 min" in i["detalle"] for i in items)
    assert client.get(f"/excepciones/bandeja?desde={hoy}&hasta={hoy}", headers=H["trabajador"]).status_code == 403


def test_umbral_configurable_en_reglas():
    from app.rules import efectivas
    assert efectivas({})["marcacion_offline"]["umbral_diferida_min"] == 15
    assert efectivas({"marcacion_offline": {"umbral_diferida_min": 30}})["marcacion_offline"]["umbral_diferida_min"] == 30
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        efectivas({"marcacion_offline": {"umbral_diferida_min": -1}})


def test_periodo_cerrado_rechaza_marca_diferida_409(client, H, db, trab):
    """Marca hecha offline en un mes ya cerrado: 409 y no se guarda (la PWA la muestra como rechazada)."""
    admin = db.scalar(select(Usuario).where(Usuario.email == "admin@demo.gcb.pe"))
    db.add(CierrePeriodo(empresa_id=trab.empresa_id, periodo="2024-02", cerrado_por=admin.id, estado="cerrado"))
    db.commit()
    idem = str(uuid.uuid4())
    body = {"tipo": "entrada", "ts_cliente": "2024-02-15T08:01:00-05:00", "offline": True, "id_idempotente": idem}
    r = client.post("/marcas/", json=body, headers=H["trabajador"])
    assert r.status_code == 409 and "cerrado" in r.json()["detail"]
    assert db.query(Marca).filter(Marca.id_idempotente == idem).count() == 0