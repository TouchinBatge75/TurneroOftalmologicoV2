
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    Operador,
    OperadorArea,
    Sede,
    Area,
    SedeArea
)


bp_admin_operador_areas = Blueprint(
    'admin_operador_areas',
    __name__,
    url_prefix='/api/admin/operador-areas'
)


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def verificar_administrador():
    return (
        current_user.is_authenticated
        and current_user.is_active
        and current_user.rol == 'ADMIN'
    )


def respuesta_error(mensaje, codigo=400):
    return jsonify({
        'success': False,
        'error': mensaje
    }), codigo


def validar_asignacion(operador_id, sede_id, area_id):
    """
    Valida operador, sede y área.

    No modifica registros.
    """

    operador = db.session.get(Operador, operador_id)

    if not operador:
        return 'Operador no encontrado', 404

    if not operador.activo:
        return 'El operador está inactivo', 409

    sede = db.session.get(Sede, sede_id)

    if not sede or not sede.activo:
        return 'La sede no está disponible', 409

    if operador.sede_id != sede_id:
        return (
            'El operador no pertenece a la sede indicada',
            403
        )

    area = db.session.get(Area, area_id)

    if not area or not area.activo:
        return 'El área no está disponible', 409

    sede_area = (
        SedeArea.query
        .filter(
            SedeArea.sede_id == sede_id,
            SedeArea.area_id == area_id,
            SedeArea.activo.is_(True)
        )
        .first()
    )

    if not sede_area:
        return (
            'El área no está habilitada en esta sede',
            409
        )

    return None


# ============================================================
# GET - CONSULTAR ASIGNACIONES
# ============================================================

@bp_admin_operador_areas.route('', methods=['GET'])
@login_required
def listar_asignaciones():

    if not verificar_administrador():
        return respuesta_error('Acceso no autorizado', 403)

    try:
        consulta = OperadorArea.query

        sede_id = request.args.get('sede_id', type=int)
        operador_id = request.args.get('operador_id', type=int)
        area_id = request.args.get('area_id', type=int)

        if sede_id is not None:
            consulta = consulta.filter_by(sede_id=sede_id)

        if operador_id is not None:
            consulta = consulta.filter_by(
                operador_id=operador_id
            )

        if area_id is not None:
            consulta = consulta.filter_by(area_id=area_id)

        registros = (
            consulta
            .order_by(
                OperadorArea.sede_id,
                OperadorArea.operador_id,
                OperadorArea.area_id
            )
            .all()
        )

        return jsonify({
            'success': True,
            'total': len(registros),
            'asignaciones': [
                registro.to_dict()
                for registro in registros
            ]
        }), 200

    except Exception:
        db.session.rollback()
        return respuesta_error(
            'No se pudieron consultar las asignaciones',
            500
        )


# ============================================================
# GET - CONFIGURACIÓN DISPONIBLE
# ============================================================

@bp_admin_operador_areas.route(
    '/configuracion',
    methods=['GET']
)
@login_required
def configuracion():

    if not verificar_administrador():
        return respuesta_error('Acceso no autorizado', 403)

    try:
        operadores = (
            Operador.query
            .filter(Operador.activo.is_(True))
            .order_by(Operador.nombre)
            .all()
        )

        sedes = (
            Sede.query
            .filter(Sede.activo.is_(True))
            .order_by(Sede.nombre)
            .all()
        )

        areas_sede = (
            SedeArea.query
            .join(Area, Area.id == SedeArea.area_id)
            .join(Sede, Sede.id == SedeArea.sede_id)
            .filter(
                SedeArea.activo.is_(True),
                Area.activo.is_(True),
                Sede.activo.is_(True)
            )
            .all()
        )

        return jsonify({
            'success': True,
            'operadores': [
                {
                    'id': o.id,
                    'nombre': o.nombre,
                    'rol': o.rol,
                    'sede_id': o.sede_id
                }
                for o in operadores
            ],
            'sedes': [
                {
                    'id': s.id,
                    'nombre': s.nombre,
                    'codigo': s.codigo
                }
                for s in sedes
            ],
            'areas_sede': [
                {
                    'sede_id': sa.sede_id,
                    'area_id': sa.area_id,
                    'area_codigo': sa.area.codigo,
                    'area_nombre': sa.area.nombre
                }
                for sa in areas_sede
            ]
        }), 200

    except Exception:
        db.session.rollback()
        return respuesta_error(
            'No se pudo obtener la configuración',
            500
        )


# ============================================================
# POST - ASIGNAR ÁREA A OPERADOR
# ============================================================

@bp_admin_operador_areas.route('', methods=['POST'])
@login_required
def crear_asignacion():

    if not verificar_administrador():
        return respuesta_error('Acceso no autorizado', 403)

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return respuesta_error(
            'Se requiere un objeto JSON',
            400
        )

    try:
        operador_id = int(data['operador_id'])
        sede_id = int(data['sede_id'])
        area_id = int(data['area_id'])

        if any(
            isinstance(data[k], bool)
            for k in ('operador_id', 'sede_id', 'area_id')
        ):
            raise ValueError()

        if min(operador_id, sede_id, area_id) <= 0:
            raise ValueError()

    except (KeyError, ValueError, TypeError):
        return respuesta_error(
            'operador_id, sede_id y area_id '
            'deben ser enteros positivos',
            400
        )

    try:
        error = validar_asignacion(
            operador_id,
            sede_id,
            area_id
        )

        if error:
            return respuesta_error(error[0], error[1])

        existente = (
            OperadorArea.query
            .filter_by(
                operador_id=operador_id,
                sede_id=sede_id,
                area_id=area_id
            )
            .first()
        )

        if existente:
            if existente.activo:
                return respuesta_error(
                    'El operador ya tiene esta área asignada',
                    409
                )

            existente.activo = True
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Asignación reactivada',
                'asignacion': existente.to_dict()
            }), 200

        asignacion = OperadorArea(
            operador_id=operador_id,
            sede_id=sede_id,
            area_id=area_id,
            activo=True
        )

        db.session.add(asignacion)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Área asignada correctamente',
            'asignacion': asignacion.to_dict()
        }), 201

    except IntegrityError:
        db.session.rollback()
        return respuesta_error(
            'La asignación ya existe o no es válida',
            409
        )

    except Exception:
        db.session.rollback()
        return respuesta_error(
            'No se pudo guardar la asignación',
            500
        )


# ============================================================
# PATCH - ACTIVAR O DESACTIVAR ASIGNACIÓN
# ============================================================

@bp_admin_operador_areas.route(
    '/<int:asignacion_id>',
    methods=['PATCH']
)
@login_required
def cambiar_estado(asignacion_id):

    if not verificar_administrador():
        return respuesta_error('Acceso no autorizado', 403)

    data = request.get_json(silent=True)

    if (
        not isinstance(data, dict)
        or type(data.get('activo')) is not bool
    ):
        return respuesta_error(
            'El campo activo debe ser true o false',
            400
        )

    try:
        asignacion = db.session.get(
            OperadorArea,
            asignacion_id
        )

        if not asignacion:
            return respuesta_error(
                'Asignación no encontrada',
                404
            )

        nuevo_estado = data['activo']

        if nuevo_estado:
            error = validar_asignacion(
                asignacion.operador_id,
                asignacion.sede_id,
                asignacion.area_id
            )

            if error:
                return respuesta_error(
                    error[0],
                    error[1]
                )

        asignacion.activo = nuevo_estado

        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                'Asignación activada'
                if nuevo_estado
                else 'Asignación desactivada'
            ),
            'asignacion': asignacion.to_dict()
        }), 200

    except Exception:
        db.session.rollback()
        return respuesta_error(
            'No se pudo actualizar la asignación',
            500
        )
