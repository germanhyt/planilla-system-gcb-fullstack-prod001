from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit, to_dict
from ..db import get_db
from ..deps import current_user, require
from ..models import Empresa, Trabajador, Unidad, Usuario
from ..paginacion import paginar_sql, params_pagina
from ..schemas import LoginIn, PasswordUpd, PerfilUpd, UsuarioEmpresaIn, UsuarioIn, UsuarioUpd
from ..security import create_token, hash_password, verify_password

r = APIRouter(tags=["auth"])


def _ip(req: Request):
    return req.client.host if req.client else None


@r.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    u = db.scalar(select(Usuario).where(Usuario.email == body.email.lower()))
    if not u or not u.activo or not verify_password(body.password, u.password_hash):
        audit(db, u.id if u else None, "login_fallido", "usuario", u.id if u else None, None, {"email": body.email}, _ip(request))
        db.commit()
        raise HTTPException(401, "Credenciales inválidas")
    u.ultimo_login = datetime.now(timezone.utc)
    audit(db, u.id, "login_ok", "usuario", u.id, None, None, _ip(request))
    db.commit()
    return {"access_token": create_token(u.id, u.rol), "token_type": "bearer", "rol": u.rol}


@r.get("/me")
def me(u: Usuario = Depends(current_user)):
    return to_dict(u)


@r.put("/me")
def update_me(body: PerfilUpd, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(current_user)):
    antes = to_dict(u)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(u, k, v)
    audit(db, u.id, "actualizar", "perfil", u.id, antes, to_dict(u), _ip(request))
    db.commit()
    return to_dict(u)


@r.post("/me/password")
def change_password(body: PasswordUpd, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(current_user)):
    if not verify_password(body.actual, u.password_hash):
        raise HTTPException(400, "Contraseña actual incorrecta")
    u.password_hash = hash_password(body.nueva)
    audit(db, u.id, "actualizar", "password", u.id, None, None, _ip(request))
    db.commit()
    return {"ok": True}


@r.get("/me/trabajador")
def my_worker(db: Session = Depends(get_db), u: Usuario = Depends(current_user)):
    t = db.scalar(select(Trabajador).where(Trabajador.usuario_id == u.id))
    if not t:
        raise HTTPException(404, "Usuario sin ficha de trabajador")
    return to_dict(t)


def _empresa_usuario(db: Session, rol: str, unidad_id, empresa_id):
    """La unidad (jefe) debe pertenecer a la empresa del usuario; el jefe hereda la empresa de su unidad."""
    if unidad_id:
        un = db.get(Unidad, unidad_id)
        if not un:
            raise HTTPException(422, "Unidad no existe")
        if empresa_id and un.empresa_id != empresa_id:
            raise HTTPException(422, "La unidad no pertenece a la empresa del usuario")
        if rol == "jefe":
            return un.empresa_id
    if empresa_id and not db.get(Empresa, empresa_id):
        raise HTTPException(422, "Empresa no existe")
    return empresa_id


@r.get("/usuarios")
def list_users(db: Session = Depends(get_db), _: Usuario = Depends(require("admin")),
               pag: Optional[dict] = Depends(params_pagina)):
    if pag is not None:  # S8 paso 6: paginado en BD (sin password_hash en la búsqueda)
        orden = {k: getattr(Usuario, k) for k in ("id", "email", "nombre", "rol", "activo", "empresa_id", "unidad_id", "ultimo_login")}
        return paginar_sql(db, select(Usuario), pag, to_dict, buscar=(Usuario.email, Usuario.nombre, Usuario.rol),
                           orden=orden, filtros={k: getattr(Usuario, k) for k in ("rol", "activo", "empresa_id", "unidad_id")},
                           desempate=(Usuario.id,), escalar=True)
    return [to_dict(x) for x in db.scalars(select(Usuario).order_by(Usuario.id))]


@r.post("/usuarios", status_code=201)
def create_user(body: UsuarioIn, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(require("admin"))):
    if db.scalar(select(Usuario).where(Usuario.email == body.email.lower())):
        raise HTTPException(409, "Email ya registrado")
    empresa_id = _empresa_usuario(db, body.rol, body.unidad_id, body.empresa_id)
    nu = Usuario(email=body.email.lower(), password_hash=hash_password(body.password), rol=body.rol,
                 nombre=body.nombre, unidad_id=body.unidad_id, empresa_id=empresa_id)
    db.add(nu)
    db.flush()
    audit(db, u.id, "crear", "usuario", nu.id, None, to_dict(nu), _ip(request))
    db.commit()
    return to_dict(nu)


@r.put("/usuarios/{uid}")
def update_user(uid: int, body: UsuarioUpd, request: Request, db: Session = Depends(get_db), u: Usuario = Depends(require("admin"))):
    nu = db.get(Usuario, uid)
    if not nu:
        raise HTTPException(404, "Usuario no encontrado")
    antes = to_dict(nu)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(nu, k, v)
    nu.empresa_id = _empresa_usuario(db, nu.rol, nu.unidad_id, nu.empresa_id)
    audit(db, u.id, "actualizar", "usuario", nu.id, antes, to_dict(nu), _ip(request))
    db.commit()
    return to_dict(nu)


@r.put("/usuarios/{uid}/empresa")
def cambiar_empresa_usuario(uid: int, body: UsuarioEmpresaIn, request: Request, db: Session = Depends(get_db),
                            u: Usuario = Depends(require("admin"))):
    """Solo admin: fija (o quita, con null) la empresa del usuario. Un jefe debe quedar en la empresa de su unidad."""
    nu = db.get(Usuario, uid)
    if not nu:
        raise HTTPException(404, "Usuario no encontrado")
    if nu.rol == "jefe" and nu.unidad_id:
        un = db.get(Unidad, nu.unidad_id)
        if body.empresa_id != (un.empresa_id if un else None):
            raise HTTPException(422, "Un jefe debe pertenecer a la empresa de su unidad; cambie primero la unidad")
    antes = to_dict(nu)
    nu.empresa_id = _empresa_usuario(db, nu.rol, nu.unidad_id, body.empresa_id)
    audit(db, u.id, "cambiar_empresa", "usuario", nu.id, antes, to_dict(nu), _ip(request))
    db.commit()
    return to_dict(nu)
