"""Sprint 6: alcance multiempresa. Un usuario de una empresa (RRHH con empresa fija o jefe) no ve datos de la otra;
admin/RRHH corporativo pueden filtrar por empresa."""
import pytest

PER = "2026-10"


def _empresas(client, h, path="/trabajadores", **params):
    return {t["empresa_id"] for t in client.get(path, headers=h, params=params).json()}


def test_rrhh_gcb_solo_ve_trabajadores_gcb(client, H, ids):
    gcb, cav = ids["emp"]["GCBSA"], ids["emp"]["CAVAS"]
    trabs = client.get("/trabajadores", headers=H["rrhh_gcb"]).json()
    assert {t["empresa_id"] for t in trabs} == {gcb}
    assert any(t["codigo"].startswith("REF-") for t in trabs) and any(t["codigo"].startswith("PAR-") for t in trabs)
    cav_id = next(t["id"] for t in client.get("/trabajadores", headers=H["admin"]).json() if t["empresa_id"] == cav)
    assert client.get(f"/trabajadores/{cav_id}", headers=H["rrhh_gcb"]).status_code == 404
    assert [e["codigo"] for e in client.get("/empresas", headers=H["rrhh_gcb"]).json()] == ["GCBSA"]
    assert {u["codigo"] for u in client.get("/unidades", headers=H["rrhh_gcb"]).json()} == {"REF", "PARK"}


def test_jefe_gcb_solo_su_unidad_y_empresa(client, H, ids):
    trabs = client.get("/trabajadores", headers=H["jefe_refugio"]).json()
    assert trabs and {t["unidad_id"] for t in trabs} == {ids["uni"]["REF"]}
    assert client.get("/excepciones/bandeja", headers=H["jefe_refugio"], params={
        "desde": "2026-10-01", "hasta": "2026-10-31", "empresa_id": ids["emp"]["CAVAS"]}).status_code == 403
    assert client.get("/rule-sets/vigente", headers=H["jefe_refugio"], params={
        "empresa_id": ids["emp"]["CAVAS"], "fecha": "2026-10-01"}).status_code == 403


@pytest.mark.parametrize("path,params", [
    ("/reportes/consolidado-mensual", {"periodo": PER}),
    ("/reportes/conceptos-remunerativos", {"periodo": PER}),
    ("/periodos/checklist", {"periodo": PER}),
    ("/periodos/historial", {}),
    ("/bonos-nocturnos", {}),
    ("/excepciones/part-time-riesgo", {"periodo": PER}),
    ("/banco-horas/saldos", {}),
])
def test_rrhh_gcb_no_accede_a_cavas(client, H, ids, path, params):
    r = client.get(path, headers=H["rrhh_gcb"], params=params | {"empresa_id": ids["emp"]["CAVAS"]})
    assert r.status_code == 403, (path, r.status_code)


def test_export_planilla_core_otra_empresa_403(client, H, ids):
    r = client.post("/reportes/export-planilla-core", headers=H["rrhh_gcb"],
                    params={"periodo": PER, "empresa_id": ids["emp"]["CAVAS"]})
    assert r.status_code == 403


def test_rrhh_gcb_no_crea_trabajador_en_cavas(client, H, ids):
    body = {"codigo": "X-S6-1", "empresa_id": ids["emp"]["CAVAS"], "unidad_id": ids["uni"]["SISA"], "doc_numero": "S6000001",
            "nombres": "Prueba", "apellidos": "Alcance", "tipo_contrato_id": ids["tc"]["FT"], "fecha_ingreso": "2026-01-01"}
    assert client.post("/trabajadores", headers=H["rrhh_gcb"], json=body).status_code == 403
    assert not any(t["codigo"] == "X-S6-1" for t in client.get("/trabajadores", headers=H["admin"]).json())


def test_rrhh_gcb_consolidado_solo_gcb(client, H, ids):
    r = client.get("/reportes/consolidado-mensual", headers=H["rrhh_gcb"], params={"periodo": PER})
    assert r.status_code == 200
    regs = r.json()["registros"] if isinstance(r.json(), dict) else r.json()
    assert all(not x["codigo"].startswith("CAV-") for x in regs)


def test_saldos_rrhh_gcb_y_filtro_admin(client, H, ids):
    gcb = ids["emp"]["GCBSA"]
    codigos = [s["codigo"] for s in client.get("/banco-horas/saldos", headers=H["rrhh_gcb"]).json()]
    assert codigos and not any(c.startswith("CAV-") for c in codigos)
    assert _empresas(client, H["admin"], empresa_id=gcb) == {gcb}
    assert set(ids["emp"].values()) <= _empresas(client, H["rrhh"])  # RRHH corporativo ve ambas


def test_usuario_empresa_validada(client, H, ids):
    gcb = ids["emp"]["GCBSA"]
    mal = client.post("/usuarios", headers=H["admin"], json={"email": "jefe.s6.mal@demo.gcb.pe", "password": "Clave12345!",
                                                             "rol": "jefe", "nombre": "x", "unidad_id": ids["uni"]["SISA"],
                                                             "empresa_id": gcb})
    assert mal.status_code == 422
    ok = client.post("/usuarios", headers=H["admin"], json={"email": "jefe.s6.ok@demo.gcb.pe", "password": "Clave12345!",
                                                            "rol": "jefe", "nombre": "x", "unidad_id": ids["uni"]["REF"]})
    assert ok.status_code == 201 and ok.json()["empresa_id"] == gcb
