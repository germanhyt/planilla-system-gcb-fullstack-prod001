from fastapi import FastAPI
from sqlalchemy import text

from .db import engine
from .routers import auditoria, auth, bonos, horarios, maestros, marcas, reglas, regularizaciones

app = FastAPI(title="Sistema de Planillas GCB", version="0.2.0-sprint2")
for rt in [auth.r, *maestros.routers, reglas.r, bonos.r, horarios.r, marcas.r, regularizaciones.r, auditoria.r]:
    app.include_router(rt)


@app.get("/health")
def health():
    with engine.connect() as c:
        c.execute(text("select 1"))
    return {"ok": True}
