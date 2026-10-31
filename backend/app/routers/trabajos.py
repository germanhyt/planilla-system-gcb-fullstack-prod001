"""Sprint 7: estado/progreso de trabajos en segundo plano."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..alcance import empresa_fija
from ..db import get_db
from ..deps import current_user
from ..models import Trabajo, Usuario
from ..trabajos import out

router = APIRouter(prefix="/trabajos", tags=["trabajos"])


def _ver(user: Usuario, t: Trabajo):
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    fija = empresa_fija(user)
    if fija and t.empresa_id not in (None, fija) or (fija and t.empresa_id is None and t.creado_por != user.id):
        raise HTTPException(403, "Solo puede consultar trabajos de su empresa")


@router.get("/{trabajo_id}")
def ver(trabajo_id: int, db: Session = Depends(get_db), user: Usuario = Depends(current_user)):
    t = db.get(Trabajo, trabajo_id)
    if not t:
        raise HTTPException(404, "Trabajo no encontrado")
    _ver(user, t)
    return out(t)


@router.get("")
def listar(db: Session = Depends(get_db), user: Usuario = Depends(current_user)):
    if user.rol not in ("rrhh", "admin"):
        raise HTTPException(403, "No autorizado")
    q = db.query(Trabajo)
    fija = empresa_fija(user)
    if fija:
        q = q.filter(Trabajo.empresa_id == fija)
    return [out(t) for t in q.order_by(Trabajo.id.desc()).limit(50)]
