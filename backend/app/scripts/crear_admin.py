"""Alta única del primer administrador (arranque de producción).

Uso (en el contenedor api):
    docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api python -m app.scripts.crear_admin \
        --email admin@gcb.pe --nombre "Nombre Apellido"
La contraseña se pide por getpass (sin eco) o se lee de stdin si no hay TTY; nunca se imprime ni se registra.
Si ya existe un administrador no hace nada.
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from ..audit import audit
from ..db import SessionLocal
from ..models import Usuario
from ..security import hash_password

MIN_PW = 10


def crear_admin(db, email: str, nombre: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if db.scalar(select(Usuario.id).where(Usuario.rol == "admin").limit(1)):
        return False, "Ya existe un administrador; no se creó ninguno (usar la app para más usuarios)."
    if "@" not in email or not nombre.strip():
        return False, "Email o nombre inválido."
    if len(password) < MIN_PW:
        return False, f"La contraseña debe tener al menos {MIN_PW} caracteres."
    if db.scalar(select(Usuario.id).where(Usuario.email == email)):
        return False, "Ya existe un usuario con ese email."
    u = Usuario(email=email, nombre=nombre.strip(), rol="admin", activo=True, password_hash=hash_password(password))
    db.add(u)
    db.flush()
    audit(db, u.id, "crear", "usuario", u.id, None, {"email": email, "nombre": u.nombre, "rol": "admin", "origen": "cli"},
          "cli:crear_admin")
    db.commit()
    return True, f"Administrador creado: {email}"


def _leer_password() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\r\n")
    p1 = getpass.getpass("Contraseña: ")
    if p1 != getpass.getpass("Repetir contraseña: "):
        raise SystemExit("Las contraseñas no coinciden.")
    return p1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Crea el primer administrador (una sola vez).")
    ap.add_argument("--email", required=True)
    ap.add_argument("--nombre", required=True)
    a = ap.parse_args(argv)
    with SessionLocal() as db:
        if db.scalar(select(Usuario.id).where(Usuario.rol == "admin").limit(1)):
            print("Ya existe un administrador; no se creó ninguno.")
            return 0
        ok, msg = crear_admin(db, a.email, a.nombre, _leer_password())
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
