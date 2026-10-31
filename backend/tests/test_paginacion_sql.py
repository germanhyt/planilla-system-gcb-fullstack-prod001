"""S8 paso 6: paginación en la BD (WHERE + COUNT + ORDER BY estable + LIMIT/OFFSET) y nuevos listados paginados."""
import pytest

import app.paginacion as pg
from app.db import SessionLocal
from app.models import Notificacion


@pytest.fixture
def sin_memoria(monkeypatch):
    """Si algún listado convertido cae al respaldo en memoria del middleware, la prueba falla."""
    def boom(*a, **k):
        raise AssertionError("paginacion en memoria usada")
    monkeypatch.setattr(pg, "paginar", boom)


def _trab(client, H, codigo):
    return next(t for t in client.get("/trabajadores", headers=H["admin"]).json() if t["codigo"] == codigo)


@pytest.mark.parametrize("url", ["/trabajadores", "/unidades", "/empresas", "/sedes", "/usuarios", "/notificaciones",
                                 "/justificaciones", "/he-programadas"])
def test_listados_paginan_en_bd(client, H, sin_memoria, url):
    r = client.get(f"{url}?page=1&page_size=2", headers=H["admin"])
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d) == {"items", "total", "page", "page_size", "pages"} and d["page_size"] == 2 and len(d["items"]) <= 2


def test_orden_estable_y_paginas_disjuntas(client, H, sin_memoria):
    total = client.get("/trabajadores?page=1&page_size=1", headers=H["admin"]).json()["total"]
    vistos = []
    for p in range(1, -(-total // 7) + 1):  # 'area' tiene muchos empates: el desempate por id evita repetidos
        vistos += [t["id"] for t in client.get(f"/trabajadores?page={p}&page_size=7&sort=area", headers=H["admin"]).json()["items"]]
    assert len(vistos) == total == len(set(vistos))
    desc = client.get("/trabajadores?page=1&page_size=3&sort=-codigo", headers=H["admin"]).json()["items"]
    assert [t["codigo"] for t in desc] == sorted([t["codigo"] for t in desc], reverse=True)


def test_busqueda_sin_acentos_y_filtros(client, H, sin_memoria, ids):
    r = client.get("/trabajadores?page=1&page_size=200&q=SALON", headers=H["admin"]).json()  # area 'Salón'
    assert r["total"] > 0
    act = client.get("/trabajadores?page=1&page_size=1&incluir_inactivos=true&activo=true", headers=H["admin"]).json()
    todos = client.get("/trabajadores?page=1&page_size=1&incluir_inactivos=true", headers=H["admin"]).json()
    assert act["total"] <= todos["total"]
    assert client.get("/usuarios?page=1&page_size=50&rol=jefe", headers=H["admin"]).json()["items"]
    assert all(u["rol"] == "jefe" for u in client.get("/usuarios?page=1&page_size=50&rol=jefe", headers=H["admin"]).json()["items"])


def test_notificaciones_sin_tope_500(client, H, ids, sin_memoria):
    gcb = ids["emp"]["GCBSA"]
    with SessionLocal() as db:
        db.add_all([Notificacion(empresa_id=gcb, periodo="2019-01", tipo="prueba_carga", clave=f"carga-{i}",
                                 mensaje=f"Carga {i}") for i in range(520)])
        db.commit()
    try:
        r = client.get(f"/notificaciones?page=27&page_size=20&tipo=prueba_carga&empresa_id={gcb}", headers=H["admin"]).json()
        assert r["total"] == 520 and r["pages"] == 26 and r["page"] == 26 and len(r["items"]) == 20
        assert len([n for n in client.get("/notificaciones?periodo=2019-01", headers=H["admin"]).json()]) == 520
        q = client.get(f"/notificaciones?page=1&page_size=5&q=carga%20519&empresa_id={gcb}", headers=H["admin"]).json()
        assert q["total"] == 1
        cav = ids["emp"]["CAVAS"]
        assert client.get(f"/notificaciones?page=1&empresa_id={cav}&tipo=prueba_carga", headers=H["admin"]).json()["total"] == 0
        assert client.get(f"/notificaciones?page=1&empresa_id={cav}", headers=H["rrhh_gcb"]).status_code == 403
    finally:
        with SessionLocal() as db:
            db.query(Notificacion).filter(Notificacion.tipo == "prueba_carga").delete()
            db.commit()


def test_justificaciones_paginadas_filtros_y_alcance(client, H, sin_memoria):
    t1, t2 = _trab(client, H, "CAV-013"), _trab(client, H, "PAR-003")
    for t, d in ((t1, "2024-08-05"), (t1, "2024-08-06"), (t2, "2024-08-07")):
        assert client.post("/justificaciones", json={"trabajador_id": t["id"], "dia": d, "motivo": "otro"},
                           headers=H["admin"]).status_code == 201
    base = "/justificaciones?page=1&page_size=1&desde=2024-08-01&hasta=2024-08-31"
    r = client.get(base, headers=H["admin"]).json()
    assert r["total"] == 3 and r["pages"] == 3 and r["items"][0]["dia"] == "2024-08-07"  # dia desc por defecto
    assert client.get(base + "&sort=dia", headers=H["admin"]).json()["items"][0]["dia"] == "2024-08-05"
    assert client.get(base + f"&trabajador_id={t1['id']}", headers=H["admin"]).json()["total"] == 2
    assert client.get(base + "&q=" + t2["apellidos"][:4].upper(), headers=H["admin"]).json()["total"] >= 1
    assert client.get(base + "&estado=pendiente", headers=H["admin"]).json()["total"] == 0  # admin -> aprobada
    assert client.get(base, headers=H["jefe"]).json()["total"] == 2  # jefe Cavas: solo su unidad
    assert client.get(base, headers=H["rrhh_gcb"]).json()["total"] == 1  # empresa fija GCBSA (Parking)


def test_he_programadas_paginadas(client, H, sin_memoria):
    t1, t2 = _trab(client, H, "CAV-014"), _trab(client, H, "PAR-004")
    for t, d, h in ((t1, "2024-09-02", 1), (t1, "2024-09-03", 2), (t2, "2024-09-04", 3)):
        assert client.post("/he-programadas", json={"trabajador_id": t["id"], "dia": d, "horas": h}, headers=H["admin"]).status_code == 200
    base = "/he-programadas?page=1&page_size=2&desde=2024-09-01&hasta=2024-09-30"
    r = client.get(base, headers=H["admin"]).json()
    assert r["total"] == 3 and r["pages"] == 2 and len(r["items"]) == 2
    assert client.get(base + "&sort=-horas", headers=H["admin"]).json()["items"][0]["horas"] == 3.0
    assert client.get(base + "&page=2", headers=H["admin"]).json()["page"] in (1, 2)
    assert client.get(base, headers=H["jefe"]).json()["total"] == 2
    assert client.get(base, headers=H["rrhh_gcb"]).json()["total"] == 1
    assert client.get("/he-programadas", headers=H["admin"]).status_code == 422  # lista sin page exige rango
