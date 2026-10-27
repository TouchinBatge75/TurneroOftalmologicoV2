
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import and_

import secrets
import hmac

from flask import session
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    Area,
    SedeArea,
    OperadorArea,
    Notificacion,
    NotificacionLectura
)


bp_notificaciones = Blueprint(
    'notificaciones',
    __name__,
    url_prefix='/api/notificaciones'
)


# =====================================================
# NOTIFICACIONES DE RECEPCIÓN / CAJA
# =====================================================

@bp_notificaciones.route('/recepcion', methods=['GET'])
@login_required
def notificaciones_recepcion():

    # Verificar permisos del operador.
    if current_user.rol not in ('ADMIN', 'RECEPCION'):
        return jsonify({
            'success': False,
            'error': 'Acceso no autorizado'
        }), 403

    # La sede proviene de la sesión autenticada,
    # nunca de un parámetro enviado por el navegador.
    sede_id = current_user.sede_id

    if sede_id is None:
        return jsonify({
            'success': False,
            'error': 'El operador no tiene sede asignada'
        }), 403

    # Localizar el área técnica de Recepción / Caja.
    area_caja = Area.query.filter_by(
        codigo='CAJA',
        activo=True
    ).first()

    if area_caja is None:
        return jsonify({
            'success': False,
            'error': 'Área Recepción / Caja no encontrada'
        }), 404

    # Verificar que esté habilitada en la sede.
    sede_area = SedeArea.query.filter_by(
        sede_id=sede_id,
        area_id=area_caja.id,
        activo=True
    ).first()

    if sede_area is None:
        return jsonify({
            'success': False,
            'error': 'Recepción / Caja no está habilitada'
        }), 403

    # Lectura individual por operador.
    consulta = (
        db.session.query(
            Notificacion,
            NotificacionLectura.fecha_lectura
        )
        .outerjoin(
            NotificacionLectura,
            and_(
                NotificacionLectura.notificacion_id
                == Notificacion.id,
                NotificacionLectura.operador_id
                == current_user.id
            )
        )
        .filter(
            Notificacion.sede_id == sede_id,
            Notificacion.area_destino_id == area_caja.id,
            Notificacion.activo.is_(True)
        )
    )

    solo_pendientes = (
        request.args.get('pendientes', '0') == '1'
    )

    if solo_pendientes:
        consulta = consulta.filter(
            NotificacionLectura.id.is_(None)
        )

    registros = (
        consulta
        .order_by(
            Notificacion.fecha_creacion.desc(),
            Notificacion.id.desc()
        )
        .limit(100)
        .all()
    )

    resultado = []

    for notificacion, fecha_lectura in registros:
        item = notificacion.to_dict()

        item['leida'] = fecha_lectura is not None
        item['fecha_lectura'] = (
            fecha_lectura.isoformat()
            if fecha_lectura else None
        )

        resultado.append(item)

    total_pendientes = (
        db.session.query(Notificacion.id)
        .outerjoin(
            NotificacionLectura,
            and_(
                NotificacionLectura.notificacion_id
                == Notificacion.id,
                NotificacionLectura.operador_id
                == current_user.id
            )
        )
        .filter(
            Notificacion.sede_id == sede_id,
            Notificacion.area_destino_id == area_caja.id,
            Notificacion.activo.is_(True),
            NotificacionLectura.id.is_(None)
        )
        .count()
    )

    return jsonify({
        'success': True,
        'sede_id': sede_id,
        'area': 'Recepción / Caja',
        'total_mostradas': len(resultado),
        'total_pendientes': total_pendientes,
        'notificaciones': resultado
    }), 200



# ============================================================
# NOTIFICACIONES DE MIS ÁREAS AUTORIZADAS
# ============================================================

@bp_notificaciones.route('/mis-areas', methods=['GET'])
@login_required
def notificaciones_mis_areas():

    if not current_user.is_active:
        return jsonify({
            'success': False,
            'error': 'Operador inactivo'
        }), 403

    sede_id = current_user.sede_id

    if not sede_id:
        return jsonify({
            'success': False,
            'error': 'El operador no tiene sede asignada'
        }), 403

    # Obtener exclusivamente asignaciones activas,
    # pertenecientes al operador autenticado y su sede.
    asignaciones = (
        db.session.query(OperadorArea.area_id)
        .join(
            Area,
            Area.id == OperadorArea.area_id
        )
        .join(
            SedeArea,
            and_(
                SedeArea.sede_id == OperadorArea.sede_id,
                SedeArea.area_id == OperadorArea.area_id
            )
        )
        .filter(
            OperadorArea.operador_id == current_user.id,
            OperadorArea.sede_id == sede_id,
            OperadorArea.activo.is_(True),
            Area.activo.is_(True),
            SedeArea.activo.is_(True)
        )
        .all()
    )

    areas_ids = [fila[0] for fila in asignaciones]

    if not areas_ids:
        return jsonify({
            'success': True,
            'sede_id': sede_id,
            'areas_autorizadas': [],
            'total_mostradas': 0,
            'total_pendientes': 0,
            'notificaciones': []
        }), 200

    # Evitar consultar avisos de otras áreas.
    consulta = (
        db.session.query(
            Notificacion,
            NotificacionLectura.fecha_lectura
        )
        .outerjoin(
            NotificacionLectura,
            and_(
                NotificacionLectura.notificacion_id
                == Notificacion.id,
                NotificacionLectura.operador_id
                == current_user.id
            )
        )
        .filter(
            Notificacion.sede_id == sede_id,
            Notificacion.area_destino_id.in_(areas_ids),
            Notificacion.activo.is_(True)
        )
    )

    solo_pendientes = (
        request.args.get('pendientes', '0') == '1'
    )

    if solo_pendientes:
        consulta = consulta.filter(
            NotificacionLectura.id.is_(None)
        )

    registros = (
        consulta
        .order_by(
            Notificacion.fecha_creacion.desc(),
            Notificacion.id.desc()
        )
        .limit(100)
        .all()
    )

    resultado = []

    for notificacion, fecha_lectura in registros:
        item = notificacion.to_dict()
        item['leida'] = fecha_lectura is not None
        item['fecha_lectura'] = (
            fecha_lectura.isoformat()
            if fecha_lectura else None
        )
        resultado.append(item)

    total_pendientes = (
        db.session.query(Notificacion.id)
        .outerjoin(
            NotificacionLectura,
            and_(
                NotificacionLectura.notificacion_id
                == Notificacion.id,
                NotificacionLectura.operador_id
                == current_user.id
            )
        )
        .filter(
            Notificacion.sede_id == sede_id,
            Notificacion.area_destino_id.in_(areas_ids),
            Notificacion.activo.is_(True),
            NotificacionLectura.id.is_(None)
        )
        .count()
    )

    return jsonify({
        'success': True,
        'sede_id': sede_id,
        'areas_autorizadas': areas_ids,
        'total_mostradas': len(resultado),
        'total_pendientes': total_pendientes,
        'notificaciones': resultado
    }), 200


@bp_notificaciones.route('/csrf-token', methods=['GET'])
@login_required
def obtener_token_notificaciones():

    if not current_user.is_active:
        return jsonify({
            'success': False,
            'error': 'Operador inactivo'
        }), 403

    if 'csrf_notificaciones' not in session:
        session['csrf_notificaciones'] = secrets.token_urlsafe(32)

    return jsonify({
        'success': True,
        'csrf_token': session['csrf_notificaciones']
    }), 200



@bp_notificaciones.route(
    '/<int:notificacion_id>/leer',
    methods=['PATCH']
)
@login_required
def marcar_notificacion_leida(notificacion_id):

    if not current_user.is_active:
        return jsonify({
            'success': False,
            'error': 'Operador inactivo'
        }), 403

    # Protección CSRF para sesión autenticada.
    token_sesion = session.get('csrf_notificaciones')
    token_peticion = request.headers.get('X-CSRF-Token')

    if (
        not token_sesion
        or not token_peticion
        or not hmac.compare_digest(
            token_sesion,
            token_peticion
        )
    ):
        return jsonify({
            'success': False,
            'error': 'Token CSRF inválido'
        }), 403

    sede_id = current_user.sede_id

    notificacion = db.session.get(
        Notificacion,
        notificacion_id
    )

    if (
        not notificacion
        or not notificacion.activo
        or not sede_id
        or notificacion.sede_id != sede_id
    ):
        return jsonify({
            'success': False,
            'error': 'Notificación no disponible'
        }), 404

    # Verificar el permiso de área con la configuración
    # vigente de la sede y del operador.
    autorizacion = (
        db.session.query(OperadorArea.id)
        .join(
            Area,
            Area.id == OperadorArea.area_id
        )
        .join(
            SedeArea,
            and_(
                SedeArea.sede_id == OperadorArea.sede_id,
                SedeArea.area_id == OperadorArea.area_id
            )
        )
        .filter(
            OperadorArea.operador_id == current_user.id,
            OperadorArea.sede_id == sede_id,
            OperadorArea.area_id == notificacion.area_destino_id,
            OperadorArea.activo.is_(True),
            Area.activo.is_(True),
            SedeArea.activo.is_(True)
        )
        .first()
    )

    if not autorizacion:
        return jsonify({
            'success': False,
            'error': 'Notificación no disponible'
        }), 404

    lectura = NotificacionLectura.query.filter_by(
        notificacion_id=notificacion.id,
        operador_id=current_user.id
    ).first()

    if lectura:
        return jsonify({
            'success': True,
            'message': 'La notificación ya estaba leída',
            'notificacion_id': notificacion.id,
            'leida': True,
            'fecha_lectura': lectura.fecha_lectura.isoformat()
        }), 200

    try:
        lectura = NotificacionLectura(
            notificacion_id=notificacion.id,
            operador_id=current_user.id
        )

        db.session.add(lectura)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Notificación marcada como leída',
            'notificacion_id': notificacion.id,
            'leida': True,
            'fecha_lectura': lectura.fecha_lectura.isoformat()
        }), 200

    except IntegrityError:
        db.session.rollback()

        # Otra petición pudo registrar la misma lectura.
        lectura = NotificacionLectura.query.filter_by(
            notificacion_id=notificacion.id,
            operador_id=current_user.id
        ).first()

        if lectura:
            return jsonify({
                'success': True,
                'message': 'La notificación ya estaba leída',
                'notificacion_id': notificacion.id,
                'leida': True,
                'fecha_lectura': lectura.fecha_lectura.isoformat()
            }), 200

        return jsonify({
            'success': False,
            'error': 'No se pudo registrar la lectura'
        }), 409

    except Exception:
        db.session.rollback()

        return jsonify({
            'success': False,
            'error': 'No se pudo registrar la lectura'
        }), 500
