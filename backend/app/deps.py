from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import Usuario
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> Usuario:
    if not cred:
        raise HTTPException(401, "No autenticado")
    try:
        uid = int(decode_token(cred.credentials)["sub"])
    except Exception as e:
        raise HTTPException(401, "Token inválido") from e
    u = db.get(Usuario, uid)
    if not u or not u.activo:
        raise HTTPException(401, "Usuario inactivo")
    return u


def require(*roles: str):
    """RBAC: la ruta solo es accesible para los roles indicados."""
    def dep(u: Usuario = Depends(current_user)) -> Usuario:
        if u.rol not in roles:
            raise HTTPException(403, f"Rol '{u.rol}' sin permiso")
        return u
    return dep
