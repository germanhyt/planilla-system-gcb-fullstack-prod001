"""BD de pruebas aislada: se recrea '<db>_test' en cada sesión y se migra con Alembic (sin create_all)."""
import os

import psycopg
import pytest
from sqlalchemy.engine import make_url

_base = make_url(os.environ.get("DATABASE_URL", "postgresql+psycopg://planilla:planilla@localhost:5432/planilla"))
TEST_URL = os.environ.get("TEST_DATABASE_URL") or _base.set(database=f"{_base.database}_test").render_as_string(hide_password=False)
os.environ["DATABASE_URL"] = TEST_URL
_t = make_url(TEST_URL)
with psycopg.connect(host=_t.host, port=_t.port or 5432, user=_t.username, password=_t.password, dbname="postgres",
                     autocommit=True) as c:
    c.execute(f'DROP DATABASE IF EXISTS "{_t.database}" WITH (FORCE)')
    c.execute(f'CREATE DATABASE "{_t.database}"')

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
_cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
command.upgrade(_cfg, "head")

import seed  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

seed.main()
PW = settings.seed_password


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email):
    r = client.post("/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def H(client):
    """Cabeceras por rol."""
    return {rol: _login(client, f"{rol}@demo.gcb.pe") for rol in ("admin", "rrhh", "jefe", "trabajador")} | {
        "jefe_parking": _login(client, "jefe.parking@demo.gcb.pe")}


@pytest.fixture(scope="session")
def ids(client, H):
    emp = {e["codigo"]: e["id"] for e in client.get("/empresas", headers=H["admin"]).json()}
    uni = {u["codigo"]: u["id"] for u in client.get("/unidades", headers=H["admin"]).json()}
    tc = {t["codigo"]: t["id"] for t in client.get("/tipos-contrato", headers=H["admin"]).json()}
    return {"emp": emp, "uni": uni, "tc": tc}


_test_counter = 0


@pytest.fixture
def db():
    """Database session for tests that need direct DB access."""
    from app.db import SessionLocal
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def unique_id():
    """Generate unique ID for test data to avoid conflicts."""
    global _test_counter
    _test_counter += 1
    return f"T{_test_counter:06d}"
