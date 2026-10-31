"""S8: paginación/orden/búsqueda/filtros server-side (opt-in con ?page=) y alcance multiempresa."""
from app.paginacion import PAGE_SIZE_MAX


def test_sin_page_no_cambia(client, H):
    r = client.get("/trabajadores", headers=H["rrhh"])
    assert isinstance(r.json(), list)


def test_trabajadores_paginados(client, H):
    todos = client.get("/trabajadores", headers=H["rrhh"]).json()
    r = client.get("/trabajadores?page=1&page_size=5&sort=codigo", headers=H["rrhh"]).json()
    assert set(r) >= {"items", "total", "page", "page_size"} and r["total"] == len(todos) and len(r["items"]) == 5
    assert [t["codigo"] for t in r["items"]] == sorted(t["codigo"] for t in todos)[:5]
    p2 = client.get("/trabajadores?page=2&page_size=5&sort=codigo", headers=H["rrhh"]).json()
    assert not {t["id"] for t in p2["items"]} & {t["id"] for t in r["items"]}
    q = client.get("/trabajadores?page=1&page_size=50&q=CAV-", headers=H["rrhh"]).json()
    assert q["total"] >= 32 and all("CAV-" in t["codigo"] for t in q["items"])


def test_filtro_empresa_y_alcance(client, H, ids):
    gcb = ids["emp"]["GCBSA"]
    r = client.get(f"/trabajadores?page=1&page_size=200&empresa_id={gcb}", headers=H["rrhh"]).json()
    assert r["total"] > 0 and all(t["empresa_id"] == gcb for t in r["items"])
    # rrhh.gcb tiene empresa fija: aunque pida otra empresa por filtro, nunca ve filas ajenas
    cav = ids["emp"]["CAVAS"]
    s = client.get(f"/trabajadores?page=1&page_size=200&empresa_id={cav}", headers=H["rrhh_gcb"]).json()
    assert s["total"] == 0
    j = client.get("/trabajadores?page=1&page_size=200", headers=H["jefe_refugio"]).json()
    assert j["total"] > 0 and len({t["unidad_id"] for t in j["items"]}) == 1  # jefe: solo su unidad


def test_otros_listados_paginados(client, H):
    for url in ("/usuarios", "/justificaciones", "/notificaciones", "/excepciones/bandeja?desde=2026-01-01&hasta=2026-12-31"):
        sep = "&" if "?" in url else "?"
        r = client.get(f"{url}{sep}page=1&page_size=3", headers=H["admin"])
        assert r.status_code == 200, url
        d = r.json()
        assert d["page"] == 1 and d["page_size"] == 3 and len(d["items"]) <= 3 and d["total"] >= len(d["items"]), url


def test_notificaciones_leer_todas(client, H, ids):
    gcb = ids["emp"]["GCBSA"]
    client.post(f"/notificaciones/generar?periodo=2026-10&empresa_id={gcb}", headers=H["admin"])
    r = client.post(f"/notificaciones/leer-todas?empresa_id={gcb}", headers=H["rrhh_gcb"])
    assert r.status_code == 200 and r.json()["marcadas"] >= 0
    assert client.get(f"/notificaciones/conteo?empresa_id={gcb}", headers=H["rrhh_gcb"]).json()["no_leidas"] == 0
    assert client.post("/notificaciones/leer-todas", headers=H["jefe"]).status_code == 403
    cav = ids["emp"]["CAVAS"]
    assert client.post(f"/notificaciones/leer-todas?empresa_id={cav}", headers=H["rrhh_gcb"]).status_code == 403


def test_page_size_acotado_en_bd(client, H):
    r = client.get("/trabajadores?page=99&page_size=100000", headers=H["rrhh"]).json()
    assert r["page_size"] == PAGE_SIZE_MAX and r["page"] == r["pages"]
