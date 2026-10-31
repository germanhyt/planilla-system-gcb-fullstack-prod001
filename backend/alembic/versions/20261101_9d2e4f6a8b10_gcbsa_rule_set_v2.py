"""GCB SA: revertir la modificacion in situ del rule_set (S6) y publicar HE programadas como NUEVA version

Revision ID: 9d2e4f6a8b10
Revises: 7c1d2e3f4a50
Create Date: 2026-11-01 07:00:00.000000

La migracion 3b9e1c7d5a20 (S6) agrego horas_extra.destino_programadas=compensacion dentro del rule_set existente
de GCBSA, rompiendo la inmutabilidad de rule_set. Aqui (PO pt57u):
1. se restaura la version previa (se quita la clave de las versiones no marcadas) -> auditoria "restaurar";
2. se crea la version max+1 vigente desde 2026-11-01 = config vigente + destino_programadas -> auditoria "crear".
Idempotente: si ya existe la version marcada (motivo) o una version con esa vigencia, no crea otra.
"""
import json
from datetime import date

import sqlalchemy as sa
from alembic import op

revision = '9d2e4f6a8b10'
down_revision = '7c1d2e3f4a50'
branch_labels = None
depends_on = None

DESDE = date(2026, 11, 1)
MOTIVO = "PO pt57u: HE programadas GCB SA a compensacion (banco de horas)"


def _cfg(v):
    return json.loads(v) if isinstance(v, str) else (v or {})


def _audit(conn, accion, entidad_id, antes, despues):
    conn.execute(sa.text("INSERT INTO auditoria (accion, entidad, entidad_id, antes, despues) "
                         "VALUES (:a, 'rule_set', :i, CAST(:an AS jsonb), CAST(:de AS jsonb))"),
                 {"a": accion, "i": str(entidad_id), "an": json.dumps(antes), "de": json.dumps(despues)})


def aplicar(conn, codigo="GCBSA"):
    """Devuelve {"restauradas": [...ids], "creada": id|None}. Reejecutable sin efectos duplicados."""
    out = {"restauradas": [], "creada": None}
    emp = conn.execute(sa.text("SELECT id FROM empresa WHERE codigo = :c"), {"c": codigo}).scalar()
    if emp is None:
        return out
    rows = conn.execute(sa.text("SELECT id, version, valid_from, config, motivo FROM rule_set WHERE empresa_id = :e "
                                "ORDER BY valid_from"), {"e": emp}).mappings().all()
    for r in rows:
        cfg = _cfg(r["config"])
        he = cfg.get("horas_extra")
        if r["motivo"] == MOTIVO or not isinstance(he, dict) or "destino_programadas" not in he:
            continue
        valor = he.pop("destino_programadas")
        conn.execute(sa.text("UPDATE rule_set SET config = CAST(:c AS jsonb) WHERE id = :i"),
                     {"c": json.dumps(cfg), "i": r["id"]})
        _audit(conn, "restaurar", r["id"], {"horas_extra.destino_programadas": valor},
               {"horas_extra.destino_programadas": None, "motivo": "revertir modificacion in situ S6 (pt57u)"})
        out["restauradas"].append(r["id"])
    if any(r["motivo"] == MOTIVO or r["valid_from"] == DESDE for r in rows):
        return out
    base = [r for r in rows if r["valid_from"] <= DESDE]
    if not base:
        return out
    b = base[-1]
    cfg = _cfg(conn.execute(sa.text("SELECT config FROM rule_set WHERE id = :i"), {"i": b["id"]}).scalar())
    he = cfg.get("horas_extra") if isinstance(cfg.get("horas_extra"), dict) else {}
    cfg["horas_extra"] = {**he, "destino_programadas": "compensacion"}
    ver = max(r["version"] for r in rows) + 1
    nid = conn.execute(sa.text("INSERT INTO rule_set (empresa_id, version, valid_from, config, motivo) "
                               "VALUES (:e, :v, :d, CAST(:c AS jsonb), :m) RETURNING id"),
                       {"e": emp, "v": ver, "d": DESDE, "c": json.dumps(cfg), "m": MOTIVO}).scalar()
    _audit(conn, "crear", nid, {"base_rule_set_id": b["id"], "base_version": b["version"]},
           {"version": ver, "valid_from": DESDE.isoformat(), "motivo": MOTIVO, "origen": "migracion 9d2e4f6a8b10"})
    out["creada"] = nid
    return out


def upgrade():
    aplicar(op.get_bind())


def downgrade():
    conn = op.get_bind()
    emp = conn.execute(sa.text("SELECT id FROM empresa WHERE codigo = 'GCBSA'")).scalar()
    if emp is None:
        return
    for (nid,) in conn.execute(sa.text("SELECT id FROM rule_set WHERE empresa_id = :e AND motivo = :m"),
                               {"e": emp, "m": MOTIVO}).all():
        prev = conn.execute(sa.text("SELECT id FROM rule_set WHERE empresa_id = :e AND id <> :i "
                                    "ORDER BY valid_from DESC LIMIT 1"), {"e": emp, "i": nid}).scalar()
        conn.execute(sa.text("UPDATE asistencia SET rule_set_id = :p WHERE rule_set_id = :i"), {"p": prev, "i": nid})
        conn.execute(sa.text("DELETE FROM rule_set WHERE id = :i"), {"i": nid})
    conn.execute(sa.text("UPDATE rule_set SET config = jsonb_set(config, '{horas_extra,destino_programadas}', "
                         "'\"compensacion\"') WHERE empresa_id = :e AND jsonb_typeof(config->'horas_extra') = 'object'"),
                 {"e": emp})
