"""S8 paso 7: bandeja de excepciones, marcas, bolsa de horas y bonos paginados en la BD (sin respaldo en memoria)."""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select
from zoneinfo import ZoneInfo

import app.paginacion as pg
from app.db import SessionLocal
from app.models import Asistencia, BancoHorasCompensatorias, Marca, RegularizacionHE, RuleSet, Trabajador

LIMA = ZoneInfo("America/Lima")
DESDE, HASTA = "2023-05-01", "2023-05-31"


@pytest.fixture
def sin_memoria(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("paginacion en memoria usada")
    monkeypatch.setattr(pg, "paginar", boom)


def _t(db, codigo):
    return db.scalar(select(Trabajador).where(Trabajador.codigo == codigo))


def _asis(db, t, dia, trabajadas=8.0, tardanza=0, exceso=0.0):
    rs = db.scalar(select(RuleSet.id).where(RuleSet.empresa_id == t.empresa_id).limit(1))
    a = Asistencia(trabajador_id=t.id, dia_operativo=dia, periodo=dia.strftime("%Y-%m"), horas_programadas=8,
                   horas_trabajadas=trabajadas, tardanza_min=tardanza, horas_extra_25=0, horas_extra_35=0,
                   horas_nocturnas=0, exceso_no_programado=exceso, rule_set_id=rs)
    db.add(a)
    db.flush()
    return a


@pytest.fixture(scope="module")
def datos(H):
    """Mayo 2023: 12 HE no programadas, 6 tardanzas, 3 marcas fuera de geocerca, 2 diferidas (1 sobre umbral) y 1 alerta PT."""
    with SessionLocal() as db:
        c3, p3, c8 = _t(db, "CAV-003"), _t(db, "PAR-003"), _t(db, "CAV-008")
        he = []
        for i in range(12):
            t = c3 if i % 2 else p3
            a = _asis(db, t, date(2023, 5, 1) + timedelta(days=i), trabajadas=9.5, exceso=1.5)
            r = RegularizacionHE(asistencia_id=a.id, trabajador_id=t.id, horas_exceso=1.5,
                                 estado="pendiente" if i < 9 else "rechazado")
            db.add(r)
            db.flush()
            he.append(r.id)
        for i in range(6):
            _asis(db, c3, date(2023, 5, 15) + timedelta(days=i), tardanza=7 + i)
        for i in range(5):  # PT85 6 h/dia semana del 22/05 -> alerta
            _asis(db, c8, date(2023, 5, 22) + timedelta(days=i), trabajadas=6)
        for i in range(3):
            db.add(Marca(trabajador_id=c3.id, tipo="entrada", ts_servidor=datetime(2023, 5, 10 + i, 9, tzinfo=LIMA),
                         lat=-12.0, lng=-77.0, metodo="gps", validacion_estado="fuera_geocerca", distancia_m=500 + i))
        for dif in (5, 600):
            ts = datetime(2023, 5, 20, 10, tzinfo=LIMA) + timedelta(minutes=dif)
            db.add(Marca(trabajador_id=p3.id, tipo="salida", ts_servidor=ts, ts_cliente=ts - timedelta(minutes=dif),
                         lat=-12.0, lng=-77.0, metodo="gps", validacion_estado="ok", diferida=True, diferencia_min=dif))
        db.commit()
        return {"he": he, "c3": c3.id, "p3": p3.id}


def _todas(client, h, url, size=4):
    vistos, p, total = [], 1, None
    while True:
        r = client.get(f"{url}{'&' if '?' in url else '?'}page={p}&page_size={size}", headers=h)
        assert r.status_code == 200, r.text
        d = r.json()
        assert {"items", "total", "page", "page_size", "pages"} <= set(d)
        total = d["total"]
        vistos += d["items"]
        if p >= d["pages"]:
            return vistos, total
        p += 1


def test_bandeja_en_bd_equivale_a_lista_y_sin_tope(client, H, datos, sin_memoria):
    url = f"/excepciones/bandeja?desde={DESDE}&hasta={HASTA}"
    lista = client.get(url, headers=H["admin"]).json()
    pags, total = _todas(client, H["admin"], url)
    assert total == len(lista) == len(pags)
    assert [i["clave"] for i in pags] == [i["clave"] for i in lista]  # mismo orden estable
    assert {i["clave"]: i for i in pags} == {i["clave"]: i for i in lista}
    tipos = {i["tipo"] for i in lista}
    assert {"he_no_programada", "tardanza", "fuera_geocerca", "marca_diferida", "pt_alerta"} <= tipos
    claves = {i["clave"] for i in lista}
    assert all(f"he-{r}" in claves for r in datos["he"])
    assert sum(1 for i in lista if i["tipo"] == "marca_diferida") == 1  # 5 min no supera el umbral


def test_bandeja_filtros_orden_busqueda_y_resumen(client, H, datos, sin_memoria):
    base = f"/excepciones/bandeja?desde={DESDE}&hasta={HASTA}"
    d = client.get(f"{base}&page=1&page_size=5&estado=pendiente", headers=H["admin"]).json()
    assert d["total"] == 9 and len(d["items"]) == 5 and all(i["accionable"] for i in d["items"])
    assert d["resumen"]["pendientes"] == 9
    t = client.get(f"{base}&page=1&page_size=50&tipo=tardanza&sort=dia", headers=H["admin"]).json()
    assert t["total"] == 6 and [i["dia"] for i in t["items"]] == sorted(i["dia"] for i in t["items"])
    r = client.get(f"{base}&page=1&page_size=50", headers=H["admin"]).json()["resumen"]
    assert r["fuera_geocerca"] == 3 and r["pendientes"] == 9
    q = client.get(f"{base}&page=1&page_size=50&q=PAR-003", headers=H["admin"]).json()
    assert q["total"] and all(i["trabajador"]["codigo"] == "PAR-003" for i in q["items"])


def test_bandeja_alcance_jefe(client, H, datos, sin_memoria):
    d = client.get(f"/excepciones/bandeja?desde={DESDE}&hasta={HASTA}&page=1&page_size=200", headers=H["jefe"]).json()
    uni = {i["trabajador"]["unidad_id"] for i in d["items"]}
    assert len(uni) <= 1
    assert client.get(f"/excepciones/bandeja?desde={DESDE}&hasta={HASTA}&page=1", headers=H["trabajador"]).status_code == 403


def test_marcas_en_bd_con_geocerca_y_conteos(client, H, datos, sin_memoria):
    url = "/marcas/?desde=2023-05-01&hasta=2023-05-31"
    lista = client.get(url, headers=H["admin"]).json()
    pags, total = _todas(client, H["admin"], url, size=2)
    assert total == len(lista) == 5 and [m["id"] for m in pags] == [m["id"] for m in lista]
    f = client.get(f"{url}&page=1&page_size=10&geocerca=fuera", headers=H["admin"]).json()
    assert f["total"] == 3 and all(m["geocerca"] == "fuera" for m in f["items"])
    assert f["conteos"] == {"todas": 5, "dentro": 2, "fuera": 3, "sin_gps": 0}
    s = client.get(f"{url}&page=1&page_size=10&sort=distancia_m", headers=H["admin"]).json()["items"]
    ds = [m["distancia_m"] for m in s if m["distancia_m"] is not None]
    assert ds == sorted(ds)


def test_mis_marcas_paginadas(client, H, sin_memoria):
    d = client.get("/marcas/mias?desde=2026-03-01&hasta=2026-03-31&page=1&page_size=1", headers=H["trabajador"])
    assert d.status_code == 200 and set(d.json()) >= {"items", "total", "conteos"}


def test_bolsa_saldos_e_historial_en_bd(client, H, datos, sin_memoria):
    with SessionLocal() as db:
        saldo = 0.0
        for i in range(7):
            db.add(BancoHorasCompensatorias(trabajador_id=datos["c3"], fecha_movimiento=date(2023, 5, 1 + i), tipo="credito",
                                            horas=1, saldo_anterior=saldo, saldo_nuevo=saldo + 1, origen="prueba_pag"))
            saldo += 1
        db.commit()
    lista = client.get("/banco-horas/saldos?solo_con_movimientos=true", headers=H["admin"]).json()
    pags, total = _todas(client, H["admin"], "/banco-horas/saldos?solo_con_movimientos=true", size=2)
    assert total == len(lista) == len(pags) and {s["id"] for s in pags} == {s["id"] for s in lista}
    assert all(s["movimientos"] > 0 for s in pags)
    top = client.get("/banco-horas/saldos?page=1&page_size=1&sort=-movimientos", headers=H["admin"]).json()["items"][0]
    assert top["movimientos"] == max(s["movimientos"] for s in lista)
    q = client.get("/banco-horas/saldos?page=1&page_size=5&q=CAV-003", headers=H["admin"]).json()
    assert [s["codigo"] for s in q["items"]] == ["CAV-003"]
    h = client.get(f"/banco-horas/historial/{datos['c3']}?page=1&page_size=3", headers=H["admin"]).json()
    assert h["total"] >= 7 and len(h["items"]) == 3 and h["pages"] >= 3
    jefe = client.get("/banco-horas/saldos?page=1&page_size=200", headers=H["jefe"]).json()["items"]
    assert len({s["unidad_id"] for s in jefe}) <= 1


def test_bonos_paginados(client, H, sin_memoria):
    d = client.get("/bonos-nocturnos?page=1&page_size=2", headers=H["admin"])
    assert d.status_code == 200 and set(d.json()) == {"items", "total", "page", "page_size", "pages"}
