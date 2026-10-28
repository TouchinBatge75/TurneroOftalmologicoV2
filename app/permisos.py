
from functools import wraps

from flask import jsonify
from flask_login import current_user
from sqlalchemy import select

from app import db
from app.models import (
    Permiso,
    RolPermiso,
    OperadorPermiso,
    OperadorArea,
    Sede,
    Area,
    SedeArea
)


def verificar_permiso(codigo, operador=None):
    """
    Comprueba permisos individuales y por rol.

    Prioridad:
    1. Denegación o autorización individual.
    2. Permiso del rol.
    3. Denegación predeterminada.
    """

    operador = operador or current_user

    if not operador.is_authenticated:
        return False

    if not operador.is_active or not operador.activo:
        return False

    permiso = db.session.scalar(
        select(Permiso).where(
            Permiso.codigo == codigo,
            Permiso.activo.is_(True)
        )
    )

    if permiso is None:
        return False

    individual = db.session.scalar(
        select(OperadorPermiso).where(
            OperadorPermiso.operador_id == operador.id,
            OperadorPermiso.permiso_id == permiso.id
        )
    )

    if individual is not None:
        return individual.permitido is True

    rol_permiso = db.session.scalar(
        select(RolPermiso).where(
            RolPermiso.rol == operador.rol,
            RolPermiso.permiso_id == permiso.id
        )
    )

    return rol_permiso is not None


def verificar_area(operador, sede_id, area_codigo):
    """
    Comprueba asignación activa del operador,
    sede y área habilitadas.
    """

    if not operador.is_authenticated:
        return False

    if not operador.is_active or not operador.activo:
        return False

    if operador.sede_id != sede_id:
        return False

    asignacion = db.session.scalar(
        select(OperadorArea)
        .join(Sede, Sede.id == OperadorArea.sede_id)
        .join(Area, Area.id == OperadorArea.area_id)
        .join(
            SedeArea,
            (SedeArea.sede_id == OperadorArea.sede_id)
            & (SedeArea.area_id == OperadorArea.area_id)
        )
        .where(
            OperadorArea.operador_id == operador.id,
            OperadorArea.sede_id == sede_id,
            OperadorArea.activo.is_(True),
            Sede.activo.is_(True),
            Area.activo.is_(True),
            Area.codigo == area_codigo,
            SedeArea.activo.is_(True)
        )
    )

    return asignacion is not None


def requiere_permiso(codigo):
    """
    Decorador para proteger endpoints Flask.
    """

    def decorador(funcion):

        @wraps(funcion)
        def envoltura(*args, **kwargs):

            if not current_user.is_authenticated:
                return jsonify({
                    "success": False,
                    "error": "Debe iniciar sesión"
                }), 401

            if not verificar_permiso(codigo):
                return jsonify({
                    "success": False,
                    "error": "No tiene permiso para esta acción"
                }), 403

            return funcion(*args, **kwargs)

        return envoltura

    return decorador



def verificar_acceso_turno(operador, turno, codigo_permiso):
    """
    Valida que un operador pueda ejecutar una acción
    sobre un turno específico.

    Comprueba:
    - Permiso de la operación.
    - Existencia del turno.
    - Atención asociada.
    - Área asociada.
    - Sede autorizada.
    - Asignación activa del operador.
    """

    if not verificar_permiso(codigo_permiso, operador):
        return False

    if turno is None:
        return False

    if turno.atencion is None:
        return False

    if turno.area is None:
        return False

    sede_id = turno.atencion.sede_id
    area_codigo = turno.area.codigo

    if sede_id is None or not area_codigo:
        return False

    return verificar_area(
        operador,
        sede_id,
        area_codigo
    )
