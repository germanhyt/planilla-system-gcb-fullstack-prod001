"""Paginación, orden, búsqueda y filtros server-side (S8, opt-in).

Cualquier GET que devuelva una lista JSON pasa a responder ``{items, total, page, page_size}`` cuando la
petición trae ``?page=``. El endpoint ya aplicó RBAC/alcance (empresa fija, unidad del jefe) y sus propios
filtros; aquí se aplican, sobre ese resultado ya acotado:

- ``q``: búsqueda insensible a mayúsculas/acentos en todos los valores de texto (incluye objetos anidados).
- filtros de igualdad: ``empresa_id``, ``unidad_id``, ``trabajador_id``, ``estado``, ``tipo``, ``rol`` y ``activo``
  (en la fila o en ``trabajador.<campo>``); ``desde``/``hasta`` sobre ``dia``/``fecha``/``periodo``.
- ``sort``: campo (``-campo`` descendente; admite ``a.b``).
- ``page`` (1..n) y ``page_size`` (1..PAGE_SIZE_MAX, por defecto 20).
Sin ``page`` la respuesta no cambia (compatibilidad con clientes existentes).

S8 paso 6: los listados principales paginan en la BD con ``paginar_sql`` (WHERE + COUNT + ORDER BY estable +
LIMIT/OFFSET) y devuelven ya el dict, por lo que el middleware los deja pasar. El middleware queda solo como
respaldo en memoria para listados secundarios que aún devuelven una lista.
"""
import json
import unicodedata
from typing import Any
from typing import Callable, Optional
from urllib.parse import parse_qs

from fastapi import Request
from sqlalchemy import Boolean, Integer, String, cast, func, or_, select

PAGE_SIZE_MAX = 200
PAGE_SIZE_DEF = 20
FILTROS_IGUALDAD = ("empresa_id", "unidad_id", "trabajador_id", "estado", "tipo", "rol", "activo")
CAMPOS_FECHA = ("dia", "fecha", "fecha_movimiento", "periodo", "valid_from")


def _norm(s: Any) -> str:
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def _get(fila: Any, ruta: str) -> Any:
    v = fila
    for p in ruta.split("."):
        if not isinstance(v, dict):
            return None
        v = v.get(p)
    return v


def _textos(v: Any):
    if isinstance(v, dict):
        for x in v.values():
            yield from _textos(x)
    elif isinstance(v, list):
        for x in v:
            yield from _textos(x)
    elif v is not None and not isinstance(v, bool):
        yield str(v)


def _clave_orden(v: Any):
    if v is None:
        return (2, 0, "")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return (0, v, "")
    return (1, 0, _norm(v))


def _entero(v: str | None, defecto: int, minimo: int, maximo: int | None = None) -> int:
    try:
        n = int(v) if v not in (None, "") else defecto
    except ValueError:
        n = defecto
    n = max(minimo, n)
    return min(n, maximo) if maximo else n


def paginar(filas: list, params: dict[str, str]) -> dict:
    """Aplica q, filtros, orden y página a una lista de filas (dicts)."""
    out = [f for f in filas if isinstance(f, dict)] if all(isinstance(f, dict) for f in filas) else list(filas)
    q = _norm(params.get("q", "")).strip()
    if q:
        terminos = q.split()
        out = [f for f in out if all(any(t in _norm(x) for x in _textos(f)) for t in terminos)]
    for k in FILTROS_IGUALDAD:
        val = params.get(k)
        if val in (None, ""):
            continue
        def coincide(f, k=k, val=val):
            v = f.get(k) if k in f else _get(f, f"trabajador.{k}")
            if v is None and k not in f and _get(f, "trabajador") is None:
                return True  # la fila no expone el campo: el endpoint ya filtró
            return _norm(v) == _norm(val)
        out = [f for f in out if coincide(f)]
    desde, hasta = params.get("desde"), params.get("hasta")
    if desde or hasta:
        def en_rango(f):
            campo = next((c for c in CAMPOS_FECHA if f.get(c)), None)
            if not campo:
                return True
            v = str(f[campo])[: len(desde or hasta or "")]
            return (not desde or v >= desde[: len(v)]) and (not hasta or v <= hasta[: len(v)])
        out = [f for f in out if en_rango(f)]
    sort = params.get("sort")
    if sort:
        for campo in reversed([s for s in sort.split(",") if s]):
            desc = campo.startswith("-")
            c = campo.lstrip("-+")
            out.sort(key=lambda f, c=c: _clave_orden(_get(f, c)), reverse=desc)
    total = len(out)
    size = _entero(params.get("page_size"), PAGE_SIZE_DEF, 1, PAGE_SIZE_MAX)
    pages = max(1, -(-total // size))
    page = min(_entero(params.get("page"), 1, 1), pages)
    ini = (page - 1) * size
    return {"items": out[ini: ini + size], "total": total, "page": page, "page_size": size, "pages": pages}


class PaginacionMiddleware:
    """ASGI: envuelve respuestas JSON tipo lista de GET con ?page= en {items,total,page,page_size}."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "GET":
            return await self.app(scope, receive, send)
        params = {k: v[-1] for k, v in parse_qs(scope.get("query_string", b"").decode()).items()}
        if "page" not in params:
            return await self.app(scope, receive, send)
        inicio: dict = {}
        cuerpo: list[bytes] = []

        async def capturar(msg):
            if msg["type"] == "http.response.start":
                inicio.update(msg)
                return
            if msg["type"] == "http.response.body":
                cuerpo.append(msg.get("body", b""))
                if msg.get("more_body"):
                    return
                data = b"".join(cuerpo)
                headers = [(k, v) for k, v in inicio.get("headers", [])]
                ctype = next((v for k, v in headers if k.lower() == b"content-type"), b"")
                if inicio.get("status") == 200 and ctype.startswith(b"application/json"):
                    try:
                        obj = json.loads(data)
                    except ValueError:
                        obj = None
                    if isinstance(obj, list):
                        data = json.dumps(paginar(obj, params), ensure_ascii=False, default=str).encode()
                        headers = [(k, v) for k, v in headers if k.lower() != b"content-length"]
                        headers.append((b"content-length", str(len(data)).encode()))
                await send({**inicio, "headers": headers})
                await send({"type": "http.response.body", "body": data})

        await self.app(scope, receive, capturar)


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
