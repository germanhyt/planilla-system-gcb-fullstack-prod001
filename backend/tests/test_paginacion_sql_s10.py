"""S9 (pt73u): consolidado de reportes, resumen del dashboard, asignaciones, versiones de export, historial de
cierres y bolsa del trabajador paginados/agregados en la BD; sin respaldo de paginacion en memoria."""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

import app.paginacion as pg
import app.routers.reportes as rep
from app.db import SessionLocal
from app.main import app as fastapi_app
from app.models import (
    Asistencia,
    BancoHorasCompensatorias,
    BonoNocturno,
    CierrePeriodo,
    Empresa,
    ExportPlanilla,
    HorarioAsignacion,
    RuleSet,
    Trabajador,
    Usuario,
)

PER = "2023-06"
CODS = ["CAV-003", "CAV-004", "CAV-005", "CAV-006", "CAV-007", "CAV-008", "CAV-009"]


def _t(db, codigo):
    return db.scalar(select(Trabajador).where(Trabajador.codigo == codigo))


@pytest.fixture
def sin_consolidado_python(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("consolidado cargado completo en Python")
    monkeypatch.setattr(rep, "_consolidado_mensual_data", boom)


@pytest.fixture
def sin_memoria(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("paginacion en memoria usada")
    monkeypatch.setattr(pg, "paginar", boom, raising=False)


@pytest.fixture(scope="module")
def datos(H):
    with SessionLocal() as db:
        cav = db.scalar(select(Empresa.id).where(Empresa.codigo == "CAVAS"))
        admin = db.scalar(select(Usuario.id).where(Usuario.email == "admin@demo.gcb.pe"))
        rs = db.scalar(select(RuleSet.id).where(RuleSet.empresa_id == cav).limit(1))
        ts = [_t(db, c) for c in CODS]
        for i, t in enumerate(ts):
            for d in range(1, 4 + i % 3):
                trab = 0 if (i == 2 and d == 1) else 8 + (i % 4) * 0.25 + d * 0.33
                db.add(Asistencia(trabajador_id=t.id, dia_operativo=date(2023, 6, d + 2 * i), periodo=PER,
                                  horas_programadas=8, horas_trabajadas=trab, tardanza_min=(i * d) % 7,
                                  horas_extra_25=0.33 * (d % 2), horas_extra_35=0.17 * (i % 2), horas_nocturnas=1.11 * (i % 3),
                                  exceso_no_programado=0, rule_set_id=rs))
        solo_bono = _t(db, "CAV-010")
        db.add(BonoNocturno(trabajador_id=solo_bono.id, periodo=PER, cantidad=3, monto=45.5, estado="aprobado",
                            registrado_por=admin))
        db.add(BonoNocturno(trabajador_id=ts[0].id, periodo=PER, cantidad=2, monto=30, estado="aprobado", registrado_por=admin))
        for f, tipo, h, ant, nue in ((date(2023, 5, 30), "credito", 2, 0, 2), (date(2023, 6, 10), "credito", 3, 2, 5),
                                     (date(2023, 6, 20), "debito", 1, 5, 4), (date(2023, 7, 2), "credito", 9, 4, 13)):
            db.add(BancoHorasCompensatorias(trabajador_id=ts[1].id, fecha_movimiento=f, tipo=tipo, horas=h,
                                            saldo_anterior=ant, saldo_nuevo=nue, origen="test s10"))
        for i in range(5):
            db.add(HorarioAsignacion(trabajador_id=ts[3].id, vigente_desde=date(2020, 1 + i, 1),
                                     vigente_hasta=date(2020, 1 + i, 28), patron=[[None] * 7], nota=f"s10-{i}", creado_por=admin))
        for i in range(5):
            db.add(ExportPlanilla(empresa_id=cav, periodo=f"2019-0{1 + i % 2}", formato="csv", version=1 + i // 2,
                                  estado="PRELIMINAR", layout_version="PC-ASIS-1.2", checksum=f"s10{i}".ljust(64, "0"),
                                  archivo=f"s10_{i}.csv", contenido="x", generado_por=admin))
        for i in range(5):
            db.add(CierrePeriodo(empresa_id=cav, periodo=f"2018-0{1 + i}", cerrado_por=admin, estado="cerrado",
                                 cerrado_en=datetime(2018, 2 + i, 1, tzinfo=timezone.utc)))
        db.commit()
        return {"cav": cav, "asig_t": ts[3].id}


def _todas(client, h, url, size=3):
    vistos, p = [], 1
    while True:
        r = client.get(f"{url}{'&' if '?' in url else '?'}page={p}&page_size={size}", headers=h)
        assert r.status_code == 200, r.text
        d = r.json()
        assert {"items", "total", "page", "page_size", "pages"} <= set(d), d
        vistos += d["items"]
        if p >= d["pages"]:
            return vistos, d
        p += 1


def test_consolidado_paginado_en_bd_igual_al_completo(client, H, datos, monkeypatch):
    url = f"/reportes/consolidado-mensual?periodo={PER}&empresa_id={datos['cav']}"
    clasico = client.get(url, headers=H["rrhh"]).json()
    assert len(clasico["registros"]) == 8
    monkeypatch.setattr(rep, "_consolidado_mensual_data", lambda *a, **k: (_ for _ in ()).throw(AssertionError("python")))
    items, ult = _todas(client, H["rrhh"], url)
    assert ult["total"] == 8
    por_id = {r["trabajador_id"]: r for r in clasico["registros"]}
    assert [i["codigo"] for i in items] == [r["codigo"] for r in clasico["registros"]]
    for i in items:
        assert i == por_id[i["trabajador_id"]]
    assert ult["totales"] == clasico["totales"]
    assert ult["periodo"] == PER and ult["desde"] == "2023-06-01" and "periodo_cerrado" in ult
    bono = next(i for i in items if i["codigo"] == "CAV-010")
    assert bono["bono_3am"] == 3 and bono["bono_3am_monto"] == 45.5 and bono["horas_trabajadas"] == 0
    c4 = next(i for i in items if i["codigo"] == "CAV-004")
    assert c4["banco_horas_saldo"] == 4 and c4["banco_horas_mes"] == 2


def test_consolidado_orden_y_busqueda_en_bd(client, H, datos, sin_consolidado_python):
    base = f"/reportes/consolidado-mensual?periodo={PER}&empresa_id={datos['cav']}&page=1&page_size=50"
    d = client.get(base + "&sort=-horas_trabajadas", headers=H["rrhh"]).json()
    hs = [i["horas_trabajadas"] for i in d["items"]]
    assert hs == sorted(hs, reverse=True)
    q = client.get(base + "&q=cav-00", headers=H["rrhh"]).json()
    assert q["total"] == 7 and all(i["codigo"].startswith("CAV-00") for i in q["items"])
    j = client.get(f"/reportes/consolidado-mensual?periodo={PER}&page=1", headers=H["jefe"]).json()
    with SessionLocal() as db:
        uni = db.scalar(select(Usuario.unidad_id).where(Usuario.email == "jefe@demo.gcb.pe"))
    assert all(i["unidad_id"] == uni for i in j["items"])


def test_resumen_mensual_dashboard_agregado_en_sql(client, H, datos, sin_consolidado_python):
    r = client.get(f"/reportes/resumen-mensual?periodos={PER},2023-07&empresa_id={datos['cav']}", headers=H["rrhh"])
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d) == {PER, "2023-07"}
    pag_tot = client.get(f"/reportes/consolidado-mensual?periodo={PER}&empresa_id={datos['cav']}&page=1",
                                  headers=H["rrhh"]).json()["totales"]
    for k, v in pag_tot.items():
        assert d[PER][k] == v, k
    assert d[PER]["total_ausencias"] == 1


def test_resumen_mensual_igual_al_clasico(client, H, datos):
    cl = client.get(f"/reportes/consolidado-mensual?periodo={PER}&empresa_id={datos['cav']}", headers=H["rrhh"]).json()
    d = client.get(f"/reportes/resumen-mensual?periodos={PER}&empresa_id={datos['cav']}", headers=H["rrhh"]).json()
    assert d[PER]["total_ausencias"] == sum(r["ausencias"] for r in cl["registros"])
    assert {k: d[PER][k] for k in cl["totales"]} == cl["totales"]
    assert client.get(f"/reportes/resumen-mensual?periodos={','.join(['2023-01'] * 25)}", headers=H["rrhh"]).status_code == 422
    assert client.get("/reportes/resumen-mensual?periodos=2023-13", headers=H["rrhh"]).status_code == 422


def test_asignaciones_paginadas(client, H, datos, sin_memoria):
    url = f"/asignaciones-horario?trabajador_id={datos['asig_t']}"
    lista = client.get(url, headers=H["rrhh"]).json()
    items, ult = _todas(client, H["rrhh"], url, size=2)
    assert ult["total"] == len(lista) >= 5 and [i["id"] for i in items] == [a["id"] for a in lista]
    s = client.get(url + "&page=1&page_size=50&sort=vigente_desde", headers=H["rrhh"]).json()["items"]
    assert [a["vigente_desde"] for a in s] == sorted(a["vigente_desde"] for a in s)


def test_versiones_export_paginadas(client, H, datos, sin_memoria):
    url = f"/reportes/export-planilla-core/versiones?empresa_id={datos['cav']}"
    lista = client.get(url, headers=H["admin"]).json()
    items, ult = _todas(client, H["admin"], url, size=2)
    assert ult["total"] == len(lista) >= 5 and [i["id"] for i in items] == [v["id"] for v in lista]
    f = client.get(url + "&periodo=2019-01&page=1&page_size=50", headers=H["admin"]).json()
    assert f["total"] == 3 and all(i["periodo"] == "2019-01" for i in f["items"])
    s = client.get(url + "&page=1&page_size=50&sort=version", headers=H["admin"]).json()["items"]
    assert [i["version"] for i in s] == sorted(i["version"] for i in s)


def test_historial_cierres_paginado(client, H, datos, sin_memoria):
    url = f"/periodos/historial?empresa_id={datos['cav']}"
    lista = client.get(url, headers=H["rrhh"]).json()
    items, ult = _todas(client, H["rrhh"], url, size=2)
    assert ult["total"] == len(lista) >= 5 and [i["id"] for i in items] == [c["id"] for c in lista]
    e = client.get(url + "&page=1&page_size=50&estado=cerrado&q=2018-0", headers=H["rrhh"]).json()
    assert e["total"] == 5 and all(i["periodo"].startswith("2018-0") for i in e["items"])


def test_bolsa_del_trabajador_paginada(client, H, sin_memoria):
    d = client.get("/banco-horas/saldos?page=1&page_size=5", headers=H["trabajador"]).json()
    assert {"items", "total", "page"} <= set(d) and d["total"] <= 1
    with SessionLocal() as db:
        uid = db.scalar(select(Usuario.id).where(Usuario.email == "trabajador@demo.gcb.pe"))
        propio = db.scalar(select(Trabajador.id).where(Trabajador.usuario_id == uid))
    assert all(i["id"] == propio for i in d["items"])


def test_sin_respaldo_en_memoria(client, H):
    assert not hasattr(pg, "paginar") and not hasattr(pg, "PaginacionMiddleware")
    assert all("Paginacion" not in type(m.cls).__name__ and getattr(m.cls, "__name__", "") != "PaginacionMiddleware"
               for m in fastapi_app.user_middleware)
