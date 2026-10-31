"""Sprint 5: módulo Configuración (rule_set versionado + tipos de contrato) y semilla de configuración para prod."""
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import seed
from app.models import Base, CierrePeriodo, Empresa, RuleSet, TipoContrato, Trabajador, Usuario
from app.rules import diff


def _post(client, H, rol="admin", ruta="/rule-sets", **body):
    return client.post(ruta, headers=H[rol], json=body)


def test_preview_no_guarda_y_muestra_diff(client, H, ids):
    cav = ids["emp"]["CAVAS"]
    n = len(client.get("/rule-sets", headers=H["admin"], params={"empresa_id": cav}).json())
    cfg = {"tolerancia": {"modo": "umbral_descuenta_exceso", "minutos": 5}, "horas_extra": {"pct_pago_mixto": 70}}
    r = _post(client, H, "rrhh", "/rule-sets/preview", empresa_id=cav, valid_from="2027-03-01", config=cfg, motivo="ver")
    assert r.status_code == 200
    j = r.json()
    assert j["contra_version"] == 2
    rutas = {d["ruta"]: d for d in j["diff"]}
    assert rutas["tolerancia.modo"] == {"ruta": "tolerancia.modo", "antes": "umbral_perdona", "despues": "umbral_descuenta_exceso"}
    assert rutas["horas_extra.pct_pago_mixto"]["despues"] == 70
    # la versión vigente CAVAS separa nocturno; la nueva config no lo define -> vuelve a BASE (aparece en el diff)
    assert "nocturno.mostrar_sobretasa_separada" in rutas
    assert len(client.get("/rule-sets", headers=H["admin"], params={"empresa_id": cav}).json()) == n


def test_errores_de_validacion_estructurados(client, H, ids):
    r = _post(client, H, ruta="/rule-sets/preview", empresa_id=ids["emp"]["CAVAS"], valid_from="2027-03-01", motivo="x x",
              config={"tolerancia": {"modo": "umbral_perdona", "minutos": 500}, "horas_extra": {"pct_pago_mixto": 150}})
    assert r.status_code == 422
    campos = {e["campo"] for e in r.json()["detail"]["errores"]}
    assert {"tolerancia.minutos", "horas_extra.pct_pago_mixto"} <= campos


def test_motivo_obligatorio_y_solo_admin_publica(client, H, ids):
    body = {"empresa_id": ids["emp"]["CAVAS"], "valid_from": "2027-04-01", "config": {}}
    assert client.post("/rule-sets", headers=H["admin"], json=body).status_code == 422
    assert client.post("/rule-sets", headers=H["rrhh"], json=body | {"motivo": "rrhh no"}).status_code == 403
    assert client.post("/rule-sets/preview", headers=H["jefe"], json=body | {"motivo": "jefe"}).status_code == 403


def test_no_publica_vigencia_en_periodo_cerrado(client, H, ids, db):
    cav = ids["emp"]["CAVAS"]
    admin = db.scalar(select(Usuario.id).where(Usuario.email == "admin@demo.gcb.pe"))
    c = CierrePeriodo(empresa_id=cav, periodo="2031-05", cerrado_por=admin, estado="cerrado")
    db.add(c)
    db.commit()
    try:
        r = _post(client, H, empresa_id=cav, valid_from="2031-05-10", config={}, motivo="en cerrado")
        assert r.status_code == 409 and "cerrado" in r.json()["detail"]
    finally:
        db.delete(c)
        db.commit()


def test_publicar_version_auditada(client, H, ids):
    gcb = ids["emp"]["GCBSA"]
    r = _post(client, H, empresa_id=gcb, valid_from="2028-01-01", motivo="split mixto 60/40",
              config={"horas_extra": {"destino_default": "mixto", "pct_pago_mixto": 60}})
    assert r.status_code == 201 and r.json()["motivo"] == "split mixto 60/40"
    aud = client.get("/auditoria", headers=H["admin"], params={"entidad": "rule_set"}).json()
    assert any(a["entidad_id"] == str(r.json()["id"]) for a in aud)
    v = client.get("/rule-sets/vigente", headers=H["jefe"], params={"empresa_id": gcb, "fecha": "2028-02-01"}).json()
    assert v["efectivas"]["horas_extra"]["pct_pago_mixto"] == 60


def test_diff_puro():
    assert diff({"a": {"b": 1, "c": 2}}, {"a": {"b": 1, "c": 3}, "d": 4}) == [
        {"ruta": "a.c", "antes": 2, "despues": 3}, {"ruta": "d", "antes": None, "despues": 4}]
    assert diff({"x": 1}, {"x": 1}) == []


# --- Tipos de contrato: solo admin edita, auditado, coherencia --------------------------------
def test_tipo_contrato_edicion_admin_auditada(client, H, ids):
    tc = client.get(f"/tipos-contrato/{ids['tc']['PT102']}", headers=H["rrhh"]).json()
    body = {k: v for k, v in tc.items() if k != "id"}
    assert client.put(f"/tipos-contrato/{tc['id']}", headers=H["rrhh"], json=body).status_code == 403
    r = client.put(f"/tipos-contrato/{tc['id']}", headers=H["admin"], json=body | {"refrigerio_min": 30})
    assert r.status_code == 200 and r.json()["refrigerio_min"] == 30
    try:
        aud = client.get("/auditoria", headers=H["admin"], params={"entidad": "tipo_contrato"}).json()
        assert any(a["entidad_id"] == str(tc["id"]) and a["accion"] == "actualizar" for a in aud)
    finally:
        client.put(f"/tipos-contrato/{tc['id']}", headers=H["admin"], json=body)


@pytest.mark.parametrize("cambio", [{"refrigerio_min": 240}, {"jornada_diaria_min": 300}])
def test_tipo_contrato_incoherente_422(client, H, ids, cambio):
    tc = client.get(f"/tipos-contrato/{ids['tc']['PT85']}", headers=H["admin"]).json()
    body = {k: v for k, v in tc.items() if k != "id"} | cambio
    assert client.put(f"/tipos-contrato/{tc['id']}", headers=H["admin"], json=body).status_code == 422


# --- Semilla de configuración (prod) ------------------------------------------------------------
def test_semilla_demo_bloqueada_en_produccion(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(SystemExit):
        seed.main()


def test_semilla_config_idempotente_sin_tocar_lo_editado(db):
    antes = db.scalar(select(func.count()).select_from(RuleSet))
    seed.seed_config(db)
    seed.seed_config(db)
    db.flush()
    assert db.scalar(select(func.count()).select_from(RuleSet)) == antes
    db.rollback()


@pytest.fixture
def bd_vacia():
    """BD temporal vacía (create_all) para probar la semilla de prod desde cero."""
    import os
    url = make_url(os.environ["DATABASE_URL"])
    nombre = f"{url.database}_prodseed"
    adm = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with adm.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{nombre}"'))
    eng = create_engine(url.set(database=nombre))
    Base.metadata.create_all(eng)
    try:
        with Session(eng) as s:
            yield s
    finally:
        eng.dispose()
        with adm.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        adm.dispose()


def test_semilla_prod_solo_configuracion(bd_vacia):
    s = bd_vacia
    seed.seed_config(s)
    s.commit()
    seed.seed_config(s)  # idempotente
    s.commit()
    tcs = {t.codigo: t.refrigerio_min for t in s.scalars(select(TipoContrato))}
    assert tcs == {"FT": 45, "PT85": 45, "PT102": 45}
    rs = {(e, str(v)) for e, v in s.execute(select(Empresa.codigo, RuleSet.valid_from).join(Empresa))}
    assert rs == {("CAVAS", "2026-11-01"), ("GCBSA", "2026-01-01")}
    assert s.scalar(select(func.count()).select_from(Trabajador)) == 0
    assert s.scalar(select(func.count()).select_from(Usuario)) == 0
