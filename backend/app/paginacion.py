"""Paginación, orden, búsqueda y filtros server-side en la BD (opt-in con ``?page=``).

Los listados que lo soportan reciben ``params_pagina`` y responden ``{items, total, page, page_size, pages}`` con
``paginar_sql`` (WHERE + COUNT + ORDER BY estable + LIMIT/OFFSET), después de aplicar RBAC/alcance:

- ``q``: búsqueda insensible a mayúsculas/acentos sobre las columnas declaradas por el endpoint.
- filtros de igualdad por columna; ``desde``/``hasta`` sobre la columna de fecha del endpoint.
- ``sort``: campo permitido (``-campo`` descendente); campos desconocidos se ignoran.
- ``page`` (1..n) y ``page_size`` (1..PAGE_SIZE_MAX, por defecto 20).
Sin ``page`` la respuesta no cambia (compatibilidad con clientes existentes).

S9 (pt73u): se eliminó el middleware de respaldo que paginaba en memoria; un GET sin soporte ignora ``page``.
"""
import unicodedata
from typing import Callable, Optional

from fastapi import Request
from sqlalchemy import Boolean, Integer, String, cast, func, or_, select

PAGE_SIZE_MAX = 200
PAGE_SIZE_DEF = 20
FILTROS_IGUALDAD = ("empresa_id", "unidad_id", "trabajador_id", "estado", "tipo", "rol", "activo")


def _norm(s) -> str:
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def _entero(v: str | None, defecto: int, minimo: int, maximo: int | None = None) -> int:
    try:
        n = int(v) if v not in (None, "") else defecto
    except ValueError:
        n = defecto
    n = max(minimo, n)
    return min(n, maximo) if maximo else n


# ---------------------------------------------------------------- paginación en BD (S8 paso 6)
_CON_ACENTO, _SIN_ACENTO = "áéíóúüñàèìòùÁÉÍÓÚÜÑ", "aeiouunaeiouaeiouun"


def params_pagina(request: Request) -> Optional[dict]:
    """Dependencia FastAPI: dict de query params si la petición trae ``page``; None si no (respuesta lista)."""
    qp = request.query_params
    return {k: qp.get(k) for k in qp.keys()} if "page" in qp else None


def _plano(expr):
    return func.translate(func.lower(cast(expr, String)), _CON_ACENTO, _SIN_ACENTO)


def _valor(col, v: str):
    t = getattr(col, "type", None)
    if isinstance(t, Boolean):
        return str(v).lower() in ("1", "true", "si", "sí", "t", "yes")
    if isinstance(t, Integer):
        return int(v)
    return v


def filtrar_sql(stmt, params: dict, *, buscar=(), filtros: Optional[dict] = None, fecha=None):
    """WHERE de ``q`` (términos sin acentos), igualdad (``filtros``) y rango ``desde``/``hasta`` sobre ``fecha``."""
    q = _norm(params.get("q") or "").strip()
    if q and buscar:
        for t in q.split():
            stmt = stmt.where(or_(*[_plano(c).like(f"%{t}%") for c in buscar]))
    for k, col in (filtros or {}).items():
        v = params.get(k)
        if v not in (None, ""):
            try:
                stmt = stmt.where(col == _valor(col, v))
            except ValueError:
                stmt = stmt.where(False)
    if fecha is not None:
        if params.get("desde"):
            stmt = stmt.where(fecha >= params["desde"])
        if params.get("hasta"):
            stmt = stmt.where(fecha <= params["hasta"])
    return stmt


def paginar_sql(db, stmt, params: dict, fila: Callable, *, buscar=(), orden: Optional[dict] = None,
                filtros: Optional[dict] = None, fecha=None, desempate=(), orden_def=(), escalar: bool = False, sin_limite: bool = False) -> dict:
    """Pagina ``stmt`` (select ya acotado por RBAC/alcance) en la BD.

    - ``buscar``: columnas para ``q`` (cada término debe aparecer en alguna; sin acentos/mayúsculas).
    - ``filtros``: {param: columna} de igualdad; ``fecha``: columna para ``desde``/``hasta``.
    - ``orden``: {campo: columna} permitidos en ``sort`` (``-campo`` desc; campos desconocidos se ignoran).
    - ``desempate``: columnas únicas que se agregan al final para un orden estable entre páginas.
    - ``sin_limite``: una sola página con todo (mismo WHERE/ORDER; para la respuesta clásica en lista).
    """
    stmt = filtrar_sql(stmt, params, buscar=buscar, filtros=filtros, fecha=fecha)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    size = max(total, 1) if sin_limite else _entero(params.get("page_size"), PAGE_SIZE_DEF, 1, PAGE_SIZE_MAX)
    pages = max(1, -(-total // size))
    page = min(_entero(params.get("page"), 1, 1), pages)
    ords = []
    for campo in [s for s in (params.get("sort") or "").split(",") if s]:
        c = (orden or {}).get(campo.lstrip("-+"))
        if c is not None:
            ords.append(c.desc().nulls_last() if campo.startswith("-") else c.asc().nulls_last())
    ords += [*(orden_def if not ords else ()), *desempate]
    stmt = stmt.order_by(None).order_by(*ords).limit(size).offset((page - 1) * size)
    filas = db.scalars(stmt).all() if escalar else db.execute(stmt).all()
    return {"items": [fila(r) for r in filas], "total": total, "page": page, "page_size": size, "pages": pages}
