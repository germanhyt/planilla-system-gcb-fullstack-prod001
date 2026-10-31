from sqlalchemy import select

from ..alcance import empresa_fija
from ..crud import crud_router
from ..models import Empresa, Sede, TipoContrato, Trabajador, TurnoPlantilla, Unidad
from ..schemas import EmpresaIn, SedeIn, TipoContratoIn, TrabajadorIn, TurnoPlantillaIn, UnidadIn

LECTURA = ("jefe", "rrhh", "admin")


def scope_trabajador(q, u):
    """El jefe solo ve trabajadores de su unidad; un usuario con empresa fija, solo su empresa."""
    if u.rol == "jefe":
        q = q.where(Trabajador.unidad_id == u.unidad_id)
    fija = empresa_fija(u)
    return q.where(Trabajador.empresa_id == fija) if fija else q


def scope_empresa(q, u):
    fija = empresa_fija(u)
    return q.where(Empresa.id == fija) if fija else q


def scope_unidad(q, u):
    fija = empresa_fija(u)
    return q.where(Unidad.empresa_id == fija) if fija else q


def scope_sede(q, u):
    fija = empresa_fija(u)
    return q.where(Sede.unidad_id.in_(select(Unidad.id).where(Unidad.empresa_id == fija))) if fija else q


routers = [
    crud_router(Empresa, "/empresas", "empresa", EmpresaIn, LECTURA, ("admin",), scope=scope_empresa),
    crud_router(Unidad, "/unidades", "unidad", UnidadIn, LECTURA, ("admin",), scope=scope_unidad),
    crud_router(Sede, "/sedes", "sede", SedeIn, LECTURA, ("admin",), scope=scope_sede),
    crud_router(TipoContrato, "/tipos-contrato", "tipo_contrato", TipoContratoIn, LECTURA, ("admin",)),  # Configuración: solo admin
    crud_router(Trabajador, "/trabajadores", "trabajador", TrabajadorIn, LECTURA, ("admin", "rrhh"), scope=scope_trabajador),
    crud_router(TurnoPlantilla, "/turnos-plantilla", "turno_plantilla", TurnoPlantillaIn, LECTURA, ("admin", "rrhh")),
]
