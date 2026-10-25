
from datetime import time

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import db
from app.models import (
    Doctor,
    Consultorio,
    AsignacionDoctor,
    Sede,
    Area,
    SedeArea
)


bp_admin_asignaciones = Blueprint(
    'admin_asignaciones',
    __name__,
    url_prefix='/api/admin/asignaciones'
)


def acceso_admin():
    return current_user.rol == 'ADMIN'


def error_json(mensaje, codigo):
    return jsonify({
        'success': False,
        'error': mensaje
    }), codigo


def serializar_asignacion(asignacion):
    resultado = asignacion.to_dict()

    resultado['medico'] = asignacion.doctor.nombre
    resultado['consultorio'] = asignacion.consultorio.nombre
    resultado['codigo_consultorio'] = (
        asignacion.consultorio.codigo
    )
    resultado['sede_id'] = (
        asignacion.consultorio.sede_id
    )

    return resultado


# =====================================================
# LISTAR ASIGNACIONES
# =====================================================

@bp_admin_asignaciones.route('', methods=['GET'])
@login_required
def listar_asignaciones():

    if not acceso_admin():
        return error_json('Acceso no autorizado', 403)

    consulta = AsignacionDoctor.query

    medico_id = request.args.get(
        'doctor_id',
        type=int
    )

    sede_id = request.args.get(
        'sede_id',
        type=int
    )

    if medico_id is not None:
        consulta = consulta.filter(
            AsignacionDoctor.doctor_id == medico_id
        )

    if sede_id is not None:
        consulta = consulta.join(
            Consultorio,
            AsignacionDoctor.consultorio_id == Consultorio.id
        ).filter(
            Consultorio.sede_id == sede_id
        )

    asignaciones = consulta.order_by(
        AsignacionDoctor.dia_semana,
        AsignacionDoctor.hora_inicio,
        AsignacionDoctor.id
    ).all()

    return jsonify({
        'success': True,
        'total': len(asignaciones),
        'asignaciones': [
            serializar_asignacion(a)
            for a in asignaciones
        ]
    }), 200


# =====================================================
# CREAR ASIGNACIÓN
# =====================================================

@bp_admin_asignaciones.route('', methods=['POST'])
@login_required
def crear_asignacion():

    if not acceso_admin():
        return error_json('Acceso no autorizado', 403)

    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return error_json(
            'Se requiere un objeto JSON',
            400
        )

    try:
        doctor_id = int(datos.get('doctor_id'))
        consultorio_id = int(
            datos.get('consultorio_id')
        )
        dia_semana = int(datos.get('dia_semana'))

        hora_inicio = time.fromisoformat(
            str(datos.get('hora_inicio'))
        )
        hora_fin = time.fromisoformat(
            str(datos.get('hora_fin'))
        )

    except (ValueError, TypeError):
        return error_json(
            'Médico, consultorio, día u horario inválidos',
            400
        )

    if doctor_id <= 0 or consultorio_id <= 0:
        return error_json(
            'Identificadores inválidos',
            400
        )

    if not 0 <= dia_semana <= 6:
        return error_json(
            'El día debe estar entre 0 y 6',
            400
        )

    if hora_fin <= hora_inicio:
        return error_json(
            'La hora final debe ser posterior a la inicial',
            400
        )

    # Por ahora manejamos horarios de minuto completo.
    if (
        hora_inicio.second != 0
        or hora_fin.second != 0
        or hora_inicio.microsecond != 0
        or hora_fin.microsecond != 0
        or hora_inicio.tzinfo is not None
        or hora_fin.tzinfo is not None
    ):
        return error_json(
            'Utilice horarios locales en formato HH:MM',
            400
        )

    try:
        # PostgreSQL: serializa las escrituras realizadas
        # mediante este endpoint para evitar que dos
        # peticiones simultáneas superen la validación.
        db.session.execute(
            text('SELECT pg_advisory_xact_lock(731204, 1)')
        )

        doctor = db.session.get(Doctor, doctor_id)
        consultorio = db.session.get(
            Consultorio,
            consultorio_id
        )

        if not doctor or not doctor.activo:
            db.session.rollback()
            return error_json(
                'El médico no existe o está inactivo',
                400
            )

        if not consultorio or not consultorio.activo:
            db.session.rollback()
            return error_json(
                'El consultorio no existe o está inactivo',
                400
            )

        sede = db.session.get(
            Sede,
            consultorio.sede_id
        )
        area = db.session.get(
            Area,
            consultorio.area_id
        )

        if not sede or not sede.activo:
            db.session.rollback()
            return error_json('Sede inactiva o inválida', 400)

        if (
            not area
            or not area.activo
            or area.codigo != 'CONSULTA'
        ):
            db.session.rollback()
            return error_json(
                'El consultorio no pertenece a Consulta Médica',
                400
            )

        sede_area = SedeArea.query.filter_by(
            sede_id=consultorio.sede_id,
            area_id=consultorio.area_id,
            activo=True
        ).first()

        if not sede_area:
            db.session.rollback()
            return error_json(
                'Consulta Médica no está habilitada en la sede',
                400
            )

        # Hay conflicto si los intervalos se cruzan:
        # nuevo_inicio < existente_fin
        # y nuevo_fin > existente_inicio.
        #
        # Se revisan TODAS las sedes del médico.
        # También los médicos que usan ese consultorio.
        conflicto = (
            AsignacionDoctor.query
            .filter(
                AsignacionDoctor.activo.is_(True),
                AsignacionDoctor.dia_semana == dia_semana,
                AsignacionDoctor.hora_inicio < hora_fin,
                AsignacionDoctor.hora_fin > hora_inicio,
                db.or_(
                    AsignacionDoctor.doctor_id == doctor_id,
                    AsignacionDoctor.consultorio_id == consultorio_id
                )
            )
            .first()
        )

        if conflicto:
            db.session.rollback()

            if conflicto.doctor_id == doctor_id:
                mensaje = (
                    'El médico ya tiene una asignación '
                    'en ese horario'
                )
            else:
                mensaje = (
                    'El consultorio ya está ocupado '
                    'en ese horario'
                )

            return error_json(mensaje, 409)

        asignacion = AsignacionDoctor(
            doctor_id=doctor_id,
            consultorio_id=consultorio_id,
            dia_semana=dia_semana,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            activo=True
        )

        db.session.add(asignacion)
        db.session.flush()

        resultado = serializar_asignacion(asignacion)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Asignación registrada correctamente',
            'asignacion': resultado
        }), 201

    except IntegrityError:
        db.session.rollback()
        return error_json(
            'No fue posible registrar la asignación',
            409
        )

    except SQLAlchemyError:
        db.session.rollback()
        return error_json(
            'Error de base de datos al guardar',
            500
        )
