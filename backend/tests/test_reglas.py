def _vig(client, H, emp, fecha):
    return client.get("/rule-sets/vigente", headers=H["jefe"], params={"empresa_id": emp, "fecha": fecha})


def test_reglas_confirmadas_cavas(client, H, ids):
    e = _vig(client, H, ids["emp"]["CAVAS"], "2026-06-15").json()["efectivas"]
    assert e["dia_operativo"] == {"tipo": "operativo", "inicio": "08:00", "fin": "03:00", "corte": "06:00", "turno_cuenta_dia_inicio": True}
    assert e["periodo"] == {"tipo": "mes_calendario", "por": "dia_operativo"}
    he = e["horas_extra"]
    assert he["solo_preprogramadas"] and he["exceso_no_programado"] == "bandeja_jefe" and he["destino_default"] == "pago"
    assert [s["pct"] for s in he["sobretasas"]] == [25, 35] and he["sobretasas"][0]["hasta_horas"] == 2
    assert e["part_time"] == {"alerta_promedio_diario_horas": 4, "ventana": "semanal", "bloqueante": False}
    assert e["nocturno"]["inicio"] == "22:00" and e["nocturno"]["fin"] == "06:00" and e["nocturno"]["siempre_calcular"]
    assert e["nocturno"]["mostrar_sobretasa_separada"] is True
    assert e["tolerancia"]["modo"] in ("umbral_perdona", "umbral_descuenta_exceso", "sin_tolerancia")


def test_gcb_sa_hereda_base(client, H, ids):
    e = _vig(client, H, ids["emp"]["GCBSA"], "2026-06-15").json()["efectivas"]
    base = client.get("/rule-sets/base", headers=H["jefe"]).json()
    assert e["dia_operativo"]["tipo"] == "calendario" and e["dia_operativo"]["turno_cuenta_dia_inicio"] is True
    assert e["horas_extra"]["destino_default"] == "compensacion"
    assert e["horas_extra"]["sobretasas"] == base["horas_extra"]["sobretasas"] and e["part_time"] == base["part_time"]
    assert e["nocturno"]["mostrar_sobretasa_separada"] is False


def test_versionado_por_vigencia(client, H, ids):
    cav = ids["emp"]["CAVAS"]
    r = client.post("/rule-sets", headers=H["admin"], json={
        "empresa_id": cav, "valid_from": "2026-12-01", "motivo": "cambio tolerancia",
        "config": {"dia_operativo": {"tipo": "operativo", "inicio": "08:00", "fin": "03:00", "corte": "06:00"},
                   "tolerancia": {"modo": "umbral_descuenta_exceso", "minutos": 5}}})
    assert r.status_code == 201 and r.json()["version"] == 3
    antes = _vig(client, H, cav, "2026-11-30").json()
    despues = _vig(client, H, cav, "2026-12-01").json()
    assert antes["version"] == 2 and antes["efectivas"]["tolerancia"]["modo"] == "umbral_perdona"
    assert despues["version"] == 3 and despues["efectivas"]["tolerancia"] == {"modo": "umbral_descuenta_exceso", "minutos": 5}
    assert _vig(client, H, cav, "2025-12-31").status_code == 404


def test_vigencia_duplicada_y_config_invalida(client, H, ids):
    cav = ids["emp"]["CAVAS"]
    assert client.post("/rule-sets", headers=H["admin"], json={"empresa_id": cav, "valid_from": "2026-01-01", "config": {}}).status_code == 409
    bad = client.post("/rule-sets", headers=H["admin"], json={"empresa_id": cav, "valid_from": "2027-01-01",
                                                               "config": {"tolerancia": {"modo": "inventado", "minutos": 5}}})
    assert bad.status_code == 422
    bad2 = client.post("/rule-sets", headers=H["admin"], json={"empresa_id": cav, "valid_from": "2027-01-01",
                                                                "config": {"part_time": {"bloqueante": True}}})
    assert bad2.status_code == 422


def test_rule_set_inmutable(client, H):
    rs = client.get("/rule-sets", headers=H["admin"]).json()[0]
    assert client.put(f"/rule-sets/{rs['id']}", headers=H["admin"], json={}).status_code in (404, 405)
    assert client.delete(f"/rule-sets/{rs['id']}", headers=H["admin"]).status_code in (404, 405)
    assert client.get("/auditoria", headers=H["admin"], params={"entidad": "rule_set"}).json()


def test_cavas_reales_vigentes_desde_2026_11_01(client, H, ids):
    """Decisión PO: demo/legado hasta 2026-10-31; reglas reales CAVAS desde 2026-11-01."""
    cav = ids["emp"]["CAVAS"]
    oct_ = _vig(client, H, cav, "2026-10-31").json()
    nov = _vig(client, H, cav, "2026-11-01").json()
    assert oct_["version"] == 1 and nov["version"] == 2 and nov["valid_from"] == "2026-11-01"
    e = nov["efectivas"]
    assert e["tolerancia"] == {"modo": "umbral_perdona", "minutos": 10}
    assert e["dia_operativo"]["corte"] == "06:00" and e["horas_extra"]["destino_default"] == "pago"
    assert e["nocturno"]["mostrar_sobretasa_separada"] is True
    assert oct_["efectivas"]["dia_operativo"]["corte"] == "06:00"  # el legado sigue calculando octubre


def test_refrigerio_part_time_45(client, H):
    tcs = {t["codigo"]: t for t in client.get("/tipos-contrato", headers=H["admin"]).json()}
    assert tcs["PT85"]["refrigerio_min"] == 45 and tcs["PT102"]["refrigerio_min"] == 45
