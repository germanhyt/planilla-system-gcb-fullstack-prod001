"""Alcance multiempresa (Sprint 6).

- Usuario.empresa_id fija la empresa del usuario (RRHH/admin de una sola empresa). Null = acceso a todas.
- El jefe queda ligado a la empresa de su unidad (aunque no tenga empresa_id) y ademas solo ve su unidad.
- RRHH/admin sin empresa fija pueden filtrar con ?empresa_id=.
"""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import true
from sqlalchemy.orm import object_session

from .models import Trabajador, Unidad, Usuario


def empresa_fija(u: Usuario) -> Optional[int]:
    if u.empresa_id:
        return u.empresa_id
    if u.rol == "jefe" and u.unidad_id:
        s = object_session(u)
        un = s.get(Unidad, u.unidad_id) if s else None
        return un.empresa_id if un else None
    return None


def empresa_alcance(u: Usuario, empresa_id: Optional[int] = None) -> Optional[int]:
    """Empresa efectiva a consultar; 403 si un usuario de una empresa pide otra."""
    fija = empresa_fija(u)
    if fija and empresa_id and empresa_id != fija:
        raise HTTPException(403, "Solo puede consultar datos de su empresa")
    return fija or empresa_id


def filtro_empresa(u: Usuario, empresa_id: Optional[int] = None):
    e = empresa_alcance(u, empresa_id)
    return Trabajador.empresa_id == e if e else true()


def fuera_de_alcance(u: Usuario, t: Trabajador) -> bool:
    """True si el usuario (jefe/RRHH/admin) no puede operar sobre el trabajador t."""
    if u.rol == "jefe" and t.unidad_id != u.unidad_id:
        return True
    fija = empresa_fija(u)
    return bool(fija and t.empresa_id != fija)
