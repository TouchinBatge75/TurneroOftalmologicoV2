
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import and_

from app import db
from app.models import (
    Area,
    SedeArea,
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
