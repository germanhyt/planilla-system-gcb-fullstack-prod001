from ..crud import crud_router
from ..models import Empresa, Sede, TipoContrato, Trabajador, TurnoPlantilla, Unidad
from ..schemas import EmpresaIn, SedeIn, TipoContratoIn, TrabajadorIn, TurnoPlantillaIn, UnidadIn

LECTURA = ("jefe", "rrhh", "admin")


def scope_trabajador(q, u):
    """El jefe solo ve trabajadores de su unidad; rrhh/admin ven todo."""
    if u.rol == "jefe":
        return q.where(Trabajador.unidad_id == u.unidad_id)
    return q


routers = [
    crud_router(Empresa, "/empresas", "empresa", EmpresaIn, LECTURA, ("admin",)),
    crud_router(Unidad, "/unidades", "unidad", UnidadIn, LECTURA, ("admin",)),
    crud_router(Sede, "/sedes", "sede", SedeIn, LECTURA, ("admin",)),
    crud_router(TipoContrato, "/tipos-contrato", "tipo_contrato", TipoContratoIn, LECTURA, ("admin", "rrhh")),
    crud_router(Trabajador, "/trabajadores", "trabajador", TrabajadorIn, LECTURA, ("admin", "rrhh"), scope=scope_trabajador),
    crud_router(TurnoPlantilla, "/turnos-plantilla", "turno_plantilla", TurnoPlantillaIn, LECTURA, ("admin", "rrhh")),
]
