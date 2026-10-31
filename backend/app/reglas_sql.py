"""Valores de reglas versionadas (rule_set) como expresión SQL CASE por (empresa, día).

Permite filtrar/ordenar en la BD con umbrales que dependen de la versión de reglas vigente de cada empresa,
replicando las funciones Python (umbral_diferida, umbral_pt, corte del día operativo).
"""
from typing import Any, Callable

from sqlalchemy import and_, case, literal, select

from .models import RuleSet
from .rules import efectivas


def regla_sql(db, empresa_col, dia_expr, valor: Callable[[dict], Any], *, defecto: Any, invalida: Any = None,
              antes_primera: bool = False, tipo=None):
    """CASE: versión vigente (valid_from <= día, la más reciente). Sin versión: la primera si ``antes_primera``,
    si no ``defecto``. Config inválida: ``invalida`` (o ``defecto``)."""
    invalida = defecto if invalida is None else invalida
    lit = (lambda v: literal(v, type_=tipo)) if tipo is not None else literal
    whens, primera = [], {}
    for e, vf, cfg in db.execute(select(RuleSet.empresa_id, RuleSet.valid_from, RuleSet.config)
                                 .order_by(RuleSet.empresa_id, RuleSet.valid_from.desc())).all():
        try:
            v = valor(efectivas(cfg or {}))
        except Exception:  # noqa: BLE001 - config inválida
            v = invalida
        whens.append((and_(empresa_col == e, dia_expr >= vf), lit(v)))
        primera[e] = v
    if antes_primera:
        whens += [(empresa_col == e, lit(v)) for e, v in primera.items()]
    return case(*whens, else_=lit(defecto)) if whens else lit(defecto)
