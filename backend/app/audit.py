from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import inspect

from .models import Auditoria


def to_dict(obj, exclude=("password_hash",)) -> dict:
    out = {}
    for c in inspect(obj).mapper.column_attrs:
        if c.key in exclude:
            continue
        v = getattr(obj, c.key)
        if isinstance(v, (date, datetime, time)):
            v = v.isoformat()
        elif isinstance(v, Decimal):
            v = float(v)
        out[c.key] = v
    return out


def audit(db, usuario_id, accion, entidad, entidad_id=None, antes=None, despues=None, ip=None):
    db.add(Auditoria(usuario_id=usuario_id, accion=accion, entidad=entidad,
                     entidad_id=None if entidad_id is None else str(entidad_id), antes=antes, despues=despues, ip=ip))
