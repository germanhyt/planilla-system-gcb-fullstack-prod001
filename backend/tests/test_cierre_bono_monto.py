"""Sprint 3 / Incremento 4: monto del bono 3 AM y cierre completo de periodo (meses 2025 para no chocar)."""


def _cav(client, H, n=0):
    ts = [t for t in client.get("/trabajadores", headers=H["admin"]).json() if t["codigo"].startswith("CAV-")]
    return ts[n]


def _bono(client, H, tid, per, cantidad=3, monto=None):
    body = {"trabajador_id": tid, "periodo": per, "cantidad": cantidad}
    if monto is not None:
        body["monto"] = monto
    return client.post("/bonos-nocturnos", headers=H["admin"], json=body)


def test_bono_monto_requerido_y_en_reportes(client, H, ids):
    t, per, emp = _cav(client, H, 1), "2025-03", ids["emp"]["CAVAS"]
    b = _bono(client, H, t["id"], per).json()
    r = client.post(f"/bonos-nocturnos/{b['id']}/decision", headers=H["rrhh"], json={"aprobar": True})
    assert r.status_code == 422
    assert _bono(client, H, t["id"], per, monto=-1).status_code == 422
    b = _bono(client, H, t["id"], per, monto="75.50").json()
    assert float(b["monto"]) == 75.5 and b["estado"] == "registrado"
    ok = client.post(f"/bonos-nocturnos/{b['id']}/decision", headers=H["rrhh"], json={"aprobar": True}).json()
    assert ok["estado"] == "aprobado" and ok["aprobado_en"]
    h = client.get(f"/bonos-nocturnos/{b['id']}/historial", headers=H["admin"]).json()
    assert [float(x["monto"]) if x["monto"] is not None else None for x in h] == [None, 75.5, 75.5]
    lst = client.get("/bonos-nocturnos", params={"periodo": per, "empresa_id": emp}, headers=H["rrhh"]).json()
    assert any(x["id"] == b["id"] and x["trabajador_codigo"] == t["codigo"] for x in lst)
    c = client.get("/reportes/consolidado-mensual", params={"periodo": per, "empresa_id": emp}, headers=H["rrhh"]).json()
    fila = next(f for f in c["registros"] if f["codigo"] == t["codigo"])
    assert fila["bono_3am"] == 3 and fila["bono_3am_monto"] == 75.5
    e = client.post("/reportes/export-planilla-core", params={"periodo": per, "empresa_id": emp, "formato": "json"},
                    headers=H["rrhh"]).json()
    assert e["layout_version"] == "PC-ASIS-1.2" and e["estado"] == "PRELIMINAR"
    li = next(x for x in e["lineas"] if x["concepto_codigo"] == "B3AM" and x["trabajador_codigo"] == t["codigo"])
    assert li["cantidad"] == 3 and li["monto"] == 75.5
    csv = client.post("/reportes/export-planilla-core", params={"periodo": per, "empresa_id": emp},
                      headers=H["rrhh"]).text
    assert "cantidad;monto" in csv and ";B3AM;" in csv and "75.50" in csv


def test_checklist_cierre_confirmacion_bloqueo_reapertura(client, H, ids):
    t, per, emp = _cav(client, H, 2), "2025-05", ids["emp"]["CAVAS"]
    # marca impar (entrada sin salida) + bono sin aprobar -> pendientes
    m = client.post("/marcas/manual", headers=H["admin"], json={"trabajador_id": t["id"], "tipo": "entrada",
                    "ts_servidor": "2025-05-14T13:00:00+00:00", "razon_manual": "Prueba checklist"})
    assert m.status_code in (200, 201), m.text
    b = _bono(client, H, t["id"], per, monto=40).json()
    ck = client.get("/periodos/checklist", params={"empresa_id": emp, "periodo": per}, headers=H["rrhh"]).json()
    assert ck["cerrado"] is False and ck["conteos"]["bonos_sin_aprobar"] >= 1
    assert ck["conteos"]["marcas_incompletas"] >= 1 and ck["total_pendientes"] >= 2
    assert client.get("/periodos/checklist", params={"empresa_id": emp, "periodo": per},
                      headers=H["jefe"]).status_code == 403
    r = client.post("/periodos/cerrar", json={"empresa_id": emp, "periodo": per}, headers=H["rrhh"])
    assert r.status_code == 409 and r.json()["detail"]["conteos"]["bonos_sin_aprobar"] >= 1
    c = client.post("/periodos/cerrar", json={"empresa_id": emp, "periodo": per, "confirmar": True}, headers=H["rrhh"])
    assert c.status_code == 200 and c.json()["estado"] == "cerrado"
    cid = c.json()["id"]
    # bloqueo: bonos, decisión, marcas manuales
    assert _bono(client, H, t["id"], per, monto=10).status_code == 409
    assert client.post(f"/bonos-nocturnos/{b['id']}/decision", headers=H["rrhh"],
                       json={"aprobar": True}).status_code == 409
    m2 = client.post("/marcas/manual", headers=H["admin"], json={"trabajador_id": t["id"], "tipo": "salida",
                     "ts_servidor": "2025-05-14T22:00:00+00:00", "razon_manual": "Prueba bloqueo"})
    assert m2.status_code == 409
    # FINAL sólo con periodo cerrado
    e = client.post("/reportes/export-planilla-core", params={"periodo": per, "empresa_id": emp, "formato": "json",
                    "solo_cerrado": True}, headers=H["rrhh"])
    assert e.status_code == 200 and e.json()["estado"] == "FINAL"
    # reapertura: sólo admin y con motivo
    assert client.post(f"/periodos/reabrir/{cid}", json={"razon_reapertura": "Corregir marcas del mes"},
                       headers=H["rrhh"]).status_code == 403
    assert client.post(f"/periodos/reabrir/{cid}", json={"razon_reapertura": "corta"},
                       headers=H["admin"]).status_code == 422
    ro = client.post(f"/periodos/reabrir/{cid}", json={"razon_reapertura": "Corregir marcas del mes"},
                     headers=H["admin"])
    assert ro.status_code == 200 and ro.json()["estado"] == "reabierto"
    assert m2.status_code == 409
    m3 = client.post("/marcas/manual", headers=H["admin"], json={"trabajador_id": t["id"], "tipo": "salida",
                     "ts_servidor": "2025-05-14T22:00:00+00:00", "razon_manual": "Tras reapertura"})
    assert m3.status_code in (200, 201)
    assert client.post("/reportes/export-planilla-core", params={"periodo": per, "empresa_id": emp,
                       "solo_cerrado": True}, headers=H["rrhh"]).status_code == 409
    # re-cierre tras reapertura
    rc = client.post("/periodos/cerrar", json={"empresa_id": emp, "periodo": per, "confirmar": True},
                     headers=H["admin"])
    assert rc.status_code == 200 and rc.json()["estado"] == "cerrado" and rc.json()["id"] == cid
    aud = client.get("/periodos/historial", params={"empresa_id": emp}, headers=H["admin"]).json()
    assert any(x["periodo"] == per and x["estado"] == "cerrado" for x in aud)


def test_bloqueo_regularizacion(client, H, ids, db):
    from datetime import date

    from app.models import Asistencia, CierrePeriodo, RegularizacionHE, RuleSet
    t, emp = _cav(client, H, 3), ids["emp"]["CAVAS"]
    asi = Asistencia(trabajador_id=t["id"], dia_operativo=date(2025, 7, 10), periodo="2025-07", horas_trabajadas=10,
                     rule_set_id=db.query(RuleSet.id).filter_by(empresa_id=emp).first()[0])
    db.add(asi)
    db.flush()
    reg = RegularizacionHE(asistencia_id=asi.id, trabajador_id=t["id"], horas_exceso=2, estado="pendiente")
    db.add(reg)
    db.commit()
    c = client.post("/periodos/cerrar", json={"empresa_id": emp, "periodo": "2025-07", "confirmar": True},
                    headers=H["admin"])
    assert c.status_code == 200
    r = client.post(f"/regularizaciones/{reg.id}/decidir", json={"aprobar": True, "destino": "pago"},
                    headers=H["admin"])
    assert r.status_code == 409, r.text
    assert db.query(CierrePeriodo).filter_by(empresa_id=emp, periodo="2025-07").one().estado == "cerrado"