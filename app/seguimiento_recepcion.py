"""Seguimiento de pacientes del Turnero V2 — Recepción / Caja.

Consultas EXCLUSIVAMENTE de lectura, restringidas a la sede del operador
con permisos para Recepción/Caja. La interfaz actualiza cada 30 segundos.

No mueve turnos, no modifica pagos ni avanza recorridos.
Las fechas se almacenan en UTC sin tzinfo en la base del proyecto.
"""

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user
from sqlalchemy import case, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app import db
from app.card_atencion import diagnosticar_recorrido_atencion, obtener_estado_card
from app.models import (
    Atencion,
    AtencionServicio,
    HistorialTurno,
    RecorridoPaso,
    SolicitudArea,
    TurnoArea,
)
from app.permisos import verificar_area, verificar_permiso


bp_seguimiento_recepcion = Blueprint(
    'seguimiento_recepcion', __name__, url_prefix='/api/recepcion/seguimiento'
)

ESTADOS_TURNO_ACTIVO = ('ESPERA', 'LLAMADO', 'EN_ATENCION', 'PAUSADO')
ESTADOS_SERVICIO_TERMINADO = ('COMPLETADO', 'CANCELADO')
ESTADOS_SOLICITUD_CERRADA = ('COMPLETADA', 'CANCELADA')
UMBRAL_ESPERA_MIN = 30
LIMITE_PAGINA = 20
MAX_PAGINA = 100000


@bp_seguimiento_recepcion.before_request
def verificar_acceso_seguimiento():
    """No permite consultar pacientes de otras sedes ni a usuarios de otras áreas."""
    if not current_user.is_authenticated:
        return jsonify(success=False, error='Debe iniciar sesión'), 401
    if not current_user.is_active or not current_user.activo:
        return jsonify(success=False, error='Operador inactivo'), 403

    sede_id = current_user.sede_id
    if (
        sede_id is None
        or not verificar_permiso('recepcion_ver')
        or not verificar_area(current_user, sede_id, 'CAJA')
    ):
        return jsonify(success=False, error='Sin permiso para consultar Recepción / Caja'), 403
    return None


def _iso_utc(fecha):
    """Serializar timestamps UTC naive con zona explícita para el navegador."""
    if fecha is None:
        return None
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _minutos_transcurridos(inicio, ahora):
    if inicio is None:
        return None
    if inicio.tzinfo is not None:
        inicio = inicio.astimezone(timezone.utc).replace(tzinfo=None)
    return round(max(0.0, (ahora - inicio).total_seconds() / 60.0), 1)


def _resumen_atencion(atencion, ahora):
    """Construye la vista rápida desde datos existentes; sin alterar nada."""
    activos = sorted(
        (t for t in atencion.turnos_area if t.estado in ESTADOS_TURNO_ACTIVO),
        key=lambda t: t.id,
        reverse=True,
    )
    turno = activos[0] if activos else None
    servicios = sorted(
        atencion.servicios,
        key=lambda s: (s.orden if s.orden is not None else 999999, s.id),
    )
    pendientes = [s for s in servicios if s.estado not in ESTADOS_SERVICIO_TERMINADO]
    servicio_actual = pendientes[0] if pendientes else None
    abiertas = [
        solicitud for solicitud in atencion.solicitudes_area
        if solicitud.estado not in ESTADOS_SOLICITUD_CERRADA
    ]
    retornos = [
        solicitud for solicitud in atencion.solicitudes_area
        if solicitud.estado_retorno == 'PENDIENTE'
    ]

    minutos_area = _minutos_transcurridos(turno.fecha_entrada_cola, ahora) if turno else None
    alertas = []
    if len(activos) > 1:
        alertas.append({'codigo': 'VARIOS_TURNOS', 'texto': 'Múltiples turnos activos'})
    if abiertas:
        alertas.append({'codigo': 'SOLICITUDES', 'texto': f'{len(abiertas)} solicitud(es) abierta(s)'})
    if retornos:
        alertas.append({'codigo': 'RETORNOS', 'texto': 'Retorno pendiente'})
    if servicio_actual and servicio_actual.requiere_pago and not servicio_actual.pagado:
        alertas.append({'codigo': 'PAGO', 'texto': 'Pago pendiente'})
    if atencion.estado == 'ACTIVA' and not turno:
        alertas.append({'codigo': 'SIN_TURNO', 'texto': 'Sin turno activo'})
    if (
        turno is not None
        and turno.estado == 'ESPERA'
        and minutos_area is not None
        and minutos_area >= UMBRAL_ESPERA_MIN
    ):
        alertas.append({'codigo': 'ESPERA_LARGA', 'texto': f'Espera ≥ {UMBRAL_ESPERA_MIN} min'})

    paso = servicio_actual.paso_actual if servicio_actual else None
    area_paso = paso.area if paso else None

    return {
        'id': atencion.id,
        'folio': atencion.folio,
        'paciente_nombre': atencion.nombre_paciente,
        'estado': atencion.estado,
        'fecha_llegada': _iso_utc(atencion.fecha_hora_llegada),
        'turno_actual': (
            {
                'id': turno.id,
                'numero': turno.numero_turno,
                'area_id': turno.area_id,
                'area': turno.area.nombre if turno.area else 'Área no disponible',
                'estado': turno.estado,
                'entrada_area': _iso_utc(turno.fecha_entrada_cola),
                'minutos_en_area': minutos_area,
                'minutos_en_espera': minutos_area if turno.estado == 'ESPERA' else None,
            }
            if turno else None
        ),
        'turnos_activos': len(activos),
        'servicios_total': len(servicios),
        'servicios_pendientes': len(pendientes),
        'servicio_en_curso': (
            {
                'id': servicio_actual.id,
                'nombre': servicio_actual.servicio.nombre if servicio_actual.servicio else 'Servicio',
                'estado': servicio_actual.estado,
            }
            if servicio_actual else None
        ),
        'paso_asignado': (
            {
                'id': paso.id,
                'orden': paso.orden,
                'area': area_paso.nombre if area_paso else 'Área no disponible',
            }
            if paso else None
        ),
        'solicitudes_abiertas': len(abiertas),
        'retornos_pendientes': len(retornos),
        'alertas': alertas,
    }


@bp_seguimiento_recepcion.route('', methods=['GET'])
@bp_seguimiento_recepcion.route('/', methods=['GET'])
def listar_seguimiento():
    """Consulta paginada: activas o todas, por folio o nombre, solo sede propia."""
    try:
        estado = request.args.get('estado', 'activas').lower().strip()
        if estado not in ('activas', 'todas'):
            return jsonify(success=False, error='Filtro estado no válido'), 400

        texto_pagina = request.args.get('pagina', '1')
        try:
            pagina = int(texto_pagina)
        except (ValueError, TypeError):
            return jsonify(success=False, error='Página no válida'), 400
        if pagina < 1 or pagina > MAX_PAGINA:
            return jsonify(success=False, error='Página fuera de rango'), 400

        busqueda = request.args.get('q', '').strip()
        if len(busqueda) > 100:
            return jsonify(success=False, error='La búsqueda es demasiado larga'), 400

        consulta = Atencion.query.filter(Atencion.sede_id == current_user.sede_id)
        if estado == 'activas':
            consulta = consulta.filter(Atencion.estado == 'ACTIVA')
        if busqueda:
            # Escapar caracteres comodín para que una búsqueda sea literal.
            termino = (
                busqueda.replace('\\', '\\\\')
                .replace('%', '\\%')
                .replace('_', '\\_')
            )
            patron = f'%{termino}%'
            consulta = consulta.filter(or_(
                Atencion.folio.ilike(patron, escape='\\'),
                Atencion.nombre_paciente.ilike(patron, escape='\\'),
            ))

        total = consulta.count()
        registros = (
            consulta.options(
                selectinload(Atencion.turnos_area).selectinload(TurnoArea.area),
                selectinload(Atencion.servicios).selectinload(AtencionServicio.servicio),
                selectinload(Atencion.servicios)
                .selectinload(AtencionServicio.paso_actual)
                .selectinload(RecorridoPaso.area),
                selectinload(Atencion.solicitudes_area),
            )
            .order_by(
                case((Atencion.estado == 'ACTIVA', 0), else_=1),
                Atencion.fecha_hora_llegada.desc(),
                Atencion.id.desc(),
            )
            .offset((pagina - 1) * LIMITE_PAGINA)
            .limit(LIMITE_PAGINA)
            .all()
        )
        ahora = datetime.utcnow()
        filas = [_resumen_atencion(a, ahora) for a in registros]
        return jsonify({
            'success': True,
            'total': total,
            'pagina': pagina,
            'limite': LIMITE_PAGINA,
            'total_paginas': max(1, (total + LIMITE_PAGINA - 1) // LIMITE_PAGINA),
            'actualizado_utc': _iso_utc(ahora),
            'umbral_espera_min': UMBRAL_ESPERA_MIN,
            'atenciones': filas,
        })
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Error consultando seguimiento de atenciones')
        return jsonify(success=False, error='No fue posible consultar el seguimiento'), 500


def _recorrido_servicio(item):
    recorrido = item.recorrido
    actual = item.paso_actual
    actual_orden = actual.orden if actual and actual.recorrido_id == item.recorrido_id else None
    pasos = []
    if recorrido:
        for paso in sorted(recorrido.pasos, key=lambda p: (p.orden, p.id)):
            if actual_orden is None:
                posicion = 'SIN_POSICION'
            elif paso.id == actual.id:
                posicion = 'ACTUAL'
            elif paso.orden < actual_orden:
                # No confundir 'anterior' con 'clínicamente completado'.
                posicion = 'ANTERIOR'
            else:
                posicion = 'POSTERIOR'
            pasos.append({
                'id': paso.id,
                'orden': paso.orden,
                'area': paso.area.nombre if paso.area else 'Área no disponible',
                'tipo_paso': paso.tipo_paso,
                'posicion': posicion,
            })
    return {
        'atencion_servicio_id': item.id,
        'servicio': item.servicio.nombre if item.servicio else 'Servicio sin nombre',
        'estado': item.estado,
        'requiere_pago': item.requiere_pago,
        'pagado': item.pagado,
        'recorrido': (
            {
                'id': recorrido.id,
                'version': recorrido.version,
                'estado_publicacion': recorrido.estado_publicacion,
            }
            if recorrido else None
        ),
        'pasos': pasos,
    }


@bp_seguimiento_recepcion.route('/<int:atencion_id>', methods=['GET'])
def detalle_seguimiento(atencion_id):
    """Muestra ficha de atención, recorridos asignados e historial, solo lectura."""
    try:
        atencion = (
            Atencion.query.filter_by(id=atencion_id, sede_id=current_user.sede_id)
            .first()
        )
        if atencion is None:
            return jsonify(success=False, error='Atención no encontrada en su sede'), 404

        # Estas funciones existentes son el origen de verdad del diagnóstico.
        card = obtener_estado_card(atencion_id)
        diagnostico = diagnosticar_recorrido_atencion(atencion_id)

        items = (
            AtencionServicio.query
            .filter_by(atencion_id=atencion_id)
            .order_by(AtencionServicio.orden, AtencionServicio.id)
            .all()
        )
        turnos = (
            TurnoArea.query.filter_by(atencion_id=atencion_id)
            .order_by(TurnoArea.id.desc()).limit(30).all()
        )
        historial = (
            HistorialTurno.query.filter_by(atencion_id=atencion_id)
            .order_by(HistorialTurno.fecha_hora.desc(), HistorialTurno.id.desc())
            .limit(30).all()
        )
        solicitudes = (
            SolicitudArea.query.filter_by(atencion_id=atencion_id)
            .order_by(SolicitudArea.id.desc()).limit(30).all()
        )

        return jsonify({
            'success': True,
            'atencion': {
                'id': atencion.id,
                'folio': atencion.folio,
                'nombre_paciente': atencion.nombre_paciente,
                'estado': atencion.estado,
                'fecha_llegada': _iso_utc(atencion.fecha_hora_llegada),
                'fecha_fin': _iso_utc(atencion.fecha_hora_fin),
            },
            'card': card,
            'diagnostico': diagnostico,
            'servicios_recorridos': [_recorrido_servicio(item) for item in items],
            'turnos': [{
                'id': turno.id,
                'numero': turno.numero_turno,
                'area': turno.area.nombre if turno.area else 'Área no disponible',
                'estado': turno.estado,
                'entrada': _iso_utc(turno.fecha_entrada_cola),
                'llamado': _iso_utc(turno.fecha_llamado),
                'inicio': _iso_utc(turno.fecha_inicio),
                'fin': _iso_utc(turno.fecha_fin),
            } for turno in turnos],
            'solicitudes': [{
                'id': solicitud.id,
                'estado': solicitud.estado,
                'prioridad': solicitud.prioridad,
                'origen': solicitud.area_origen.nombre if solicitud.area_origen else 'Sistema',
                'destino': solicitud.area_destino.nombre if solicitud.area_destino else 'Área no disponible',
                'tipo_retorno': solicitud.tipo_retorno,
                'estado_retorno': solicitud.estado_retorno,
                'retorno': solicitud.area_retorno.nombre if solicitud.area_retorno else None,
            } for solicitud in solicitudes],
            'historial': [{
                'id': evento.id,
                'accion': evento.accion,
                'motivo': evento.motivo,
                'estado_anterior': evento.estado_anterior,
                'estado_nuevo': evento.estado_nuevo,
                'fecha': _iso_utc(evento.fecha_hora),
                'usuario': evento.usuario,
            } for evento in historial],
            'nota': (
                'Los pasos anteriores no se consideran completados automáticamente. '
                'El diagnóstico del recorrido es informativo y no autoriza movimientos.'
            ),
        })
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Error consultando detalle de seguimiento')
        return jsonify(success=False, error='No fue posible consultar el detalle'), 500
