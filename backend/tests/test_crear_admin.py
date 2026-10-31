"""Sprint 5: CLI de alta del primer administrador."""
import io

from sqlalchemy import select

from app.models import Auditoria, Usuario
from app.scripts import crear_admin as cli
from app.security import verify_password


def test_no_op_si_ya_hay_admin(db, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("ClaveSegura123\n"))
    assert cli.main(["--email", "otro@gcb.pe", "--nombre", "Otro"]) == 0
    out = capsys.readouterr().out
    assert "Ya existe un administrador" in out and "ClaveSegura123" not in out
    assert db.scalar(select(Usuario).where(Usuario.email == "otro@gcb.pe")) is None


def test_crea_admin_auditado_sin_password_en_logs(db):
    # Simula BD sin admin dentro de una transacción que se revierte.
    admins = db.scalars(select(Usuario).where(Usuario.rol == "admin")).all()
    for a in admins:
        a.rol = "rrhh"
    db.flush()
    orig_commit = db.commit
    db.commit = db.flush
    try:
        assert cli.crear_admin(db, "x@gcb.pe", "X", "corta")[0] is False
        ok, msg = cli.crear_admin(db, " Primer.Admin@GCB.pe ", "Primer Admin", "ClaveSegura123")
        assert ok, msg
        u = db.scalar(select(Usuario).where(Usuario.email == "primer.admin@gcb.pe"))
        assert u.rol == "admin" and verify_password("ClaveSegura123", u.password_hash)
        aud = db.scalar(select(Auditoria).where(Auditoria.entidad == "usuario", Auditoria.entidad_id == str(u.id)))
        assert aud.accion == "crear" and aud.ip == "cli:crear_admin"
        assert "ClaveSegura123" not in str(aud.despues) and "password" not in str(aud.despues)
        assert cli.crear_admin(db, "dos@gcb.pe", "Dos", "ClaveSegura123")[0] is False  # ya hay admin
    finally:
        db.commit = orig_commit
        db.rollback()
