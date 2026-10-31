from sqlalchemy import create_engine, inspect, text

from conftest import TEST_URL


def test_esquema_creado_por_alembic():
    eng = create_engine(TEST_URL)
    with eng.connect() as c:
        assert c.execute(text("select version_num from alembic_version")).scalar()
    tablas = set(inspect(eng).get_table_names())
    assert {"empresa", "unidad", "sede", "tipo_contrato", "usuario", "trabajador", "rule_set", "bono_nocturno",
            "bono_nocturno_historial", "auditoria", "turno_plantilla"} <= tablas
