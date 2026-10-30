from fastapi import FastAPI
from sqlalchemy import text

from .db import engine
from .routers import (
    asignaciones,
    auditoria,
    auth,
    banco_horas,
    bandeja,
    bonos,
    excepciones,
    he_programadas,
    horarios,
    justificaciones,
    maestros,
    marcas,
    periodos,
    reglas,
    regularizaciones,
    reportes,
)

app = FastAPI(title="Sistema de Planillas GCB", version="0.3.0-sprint3")
for rt in [
    auth.r,
    *maestros.routers,
    reglas.r,
    bonos.r,
    horarios.r,
    he_programadas.r,
    asignaciones.r,
    justificaciones.r,
    marcas.r,
    regularizaciones.r,
    auditoria.r,
    reportes.router,
    periodos.router,
    excepciones.router,
    banco_horas.router,
    bandeja.router,
    bandeja.banco,
]:
    app.include_router(rt)


@app.get("/health")
def health():
    with engine.connect() as c:
        c.execute(text("select 1"))
    return {"ok": True}
