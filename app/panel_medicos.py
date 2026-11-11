"""Turnero V2 — Panel individual de Consulta Médica (V2).

Bandeja exclusiva de turnos asignados al Doctor vinculado al Operador.
Sin alteraciones de recorridos, movimientos ni estados existentes.
"""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app import db
from app.models import (
    Area, Atencion, AtencionServicio, Consultorio, AsignacionDoctor, HistorialTurno,
    OperadorArea, SedeArea, TurnoArea,
)
from app.permisos import verificar_area, verificar_permiso

bp_panel_medicos = Blueprint('panel_medicos', __name__)

ESTADOS_ACTIVOS = ('ESPERA', 'LLAMADO', 'EN_ATENCION', 'PAUSADO')
ESTADOS_HISTORICOS = ('FINALIZADO', 'CANCELADO')
# Seguridad: no permitir que un área cualquiera acceda al panel médico.
CODIGOS_CONSULTA = {'CONSULTA', 'CONSULTA_MEDICA', 'CONSULTA_GENERAL', 'CONSULTORIOS', 'MEDICINA'}


def _fecha_utc(valor):
    if valor is None:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _inicio_jornada_utc():
    """Los datetime del proyecto están guardados en UTC sin zona.

    México central: UTC-6. Puede ajustarse con TURNERO_UTC_OFFSET_MINUTOS.
    """
    minutos = int(current_app.config.get('TURNERO_UTC_OFFSET_MINUTOS', -360))
    zona = timezone(timedelta(minutes=minutos))
    hoy_local = datetime.now(zona).date()
    medianoche_local = datetime.combine(hoy_local, datetime.min.time(), tzinfo=zona)
    return medianoche_local.astimezone(timezone.utc).replace(tzinfo=None)


def _es_consulta(area, ids_areas_consultorio):
    """Detecta Consulta Médica por código/nombre o consultorios configurados."""
    codigo = (area.codigo or '').upper()
    if codigo in {'CAJA', 'RECEPCION', 'TRABAJO_SOCIAL'}:
        return False
    nombre = (area.nombre or '').casefold()
    adicionales = current_app.config.get('TURNERO_CODIGOS_AREA_MEDICA', ())
    if isinstance(adicionales, str):
        adicionales = adicionales.split(',')
    codigos = CODIGOS_CONSULTA | {str(c).strip().upper() for c in adicionales}
    return (
        codigo in codigos or codigo.startswith('CONSULTA_')
        or 'consulta médica' in nombre or 'consulta medica' in nombre
        or 'consultorio' in nombre
        or area.id in ids_areas_consultorio
    )


def areas_medicas_autorizadas(operador):
    """Sólo áreas médicas ACTIVAS de la sede y asignadas al operador."""
    if (
        not operador.is_authenticated or not operador.is_active
        or not operador.activo or operador.sede_id is None
        or operador.rol != 'MEDICO' or not getattr(operador, 'doctor_id', None)
        or not getattr(getattr(operador, 'doctor', None), 'activo', False)
        or not verificar_permiso('turnos_ver', operador)
    ):
        return []

    # Los consultorios reconocen áreas médicas, no autorizan turnos ajenos.
    ids_consultorios = {
        area_id for (area_id,) in db.session.query(Consultorio.area_id).filter(
            Consultorio.sede_id == operador.sede_id,
            Consultorio.activo.is_(True),
        ).all()
    }
    areas = (
        db.session.query(Area)
        .join(OperadorArea, OperadorArea.area_id == Area.id)
        .join(SedeArea, (SedeArea.area_id == Area.id) & (SedeArea.sede_id == OperadorArea.sede_id))
        .filter(
            OperadorArea.operador_id == operador.id,
            OperadorArea.sede_id == operador.sede_id,
            OperadorArea.activo.is_(True),
            SedeArea.activo.is_(True),
            Area.activo.is_(True),
        )
        .order_by(Area.nombre.asc())
        .distinct().all()
    )
    asignadas = {
        c.area_id for c in (
            db.session.query(Consultorio)
            .join(AsignacionDoctor, AsignacionDoctor.consultorio_id == Consultorio.id)
            .filter(
                Consultorio.sede_id == operador.sede_id,
                Consultorio.activo.is_(True),
                AsignacionDoctor.doctor_id == operador.doctor_id,
                AsignacionDoctor.activo.is_(True),
            ).all()
        )
    }
    return [
        area for area in areas
        if area.id in asignadas
        and _es_consulta(area, ids_consultorios)
        and verificar_area(operador, operador.sede_id, area.codigo)
    ]


def operador_tiene_area_medica(operador):
    return bool(areas_medicas_autorizadas(operador))


def _consultorios_asignados(operador, area_id):
    """Horarios informativos; no interpretar dia_semana sin convención confirmada."""
    asignaciones = (
        db.session.query(AsignacionDoctor)
        .join(Consultorio, Consultorio.id == AsignacionDoctor.consultorio_id)
        .filter(
            AsignacionDoctor.doctor_id == operador.doctor_id,
            AsignacionDoctor.activo.is_(True),
            Consultorio.activo.is_(True),
            Consultorio.sede_id == operador.sede_id,
            Consultorio.area_id == area_id,
        )
        .order_by(AsignacionDoctor.dia_semana, AsignacionDoctor.hora_inicio)
        .all()
    )
    return [{
        'id': a.consultorio.id,
        'codigo': a.consultorio.codigo,
        'nombre': a.consultorio.nombre,
        'dia_semana': a.dia_semana,
        'hora_inicio': a.hora_inicio.strftime('%H:%M'),
        'hora_fin': a.hora_fin.strftime('%H:%M'),
    } for a in asignaciones]


def _autorizar_api():
    if not current_user.is_authenticated:
        return jsonify(success=False, error='Debe iniciar sesión'), 401
    if not current_user.is_active or not current_user.activo:
        return jsonify(success=False, error='Operador inactivo'), 403
    areas = areas_medicas_autorizadas(current_user)
    if not areas:
        return jsonify(success=False, error='No tiene acceso a Consulta Médica'), 403
    return areas


def _area_elegida(areas):
    raw = request.args.get('area_id')
    if raw is None or raw == '':
        return areas[0]
    try:
        area_id = int(raw)
    except (TypeError, ValueError):
        return None
    return next((a for a in areas if a.id == area_id), None)


def _turno_dict(turno, ahora):
    atencion = turno.atencion
    servicios = sorted(atencion.servicios, key=lambda s: (s.orden if s.orden is not None else 999999, s.id))
    tiempo = None
    if turno.fecha_entrada_cola:
        fin = turno.fecha_fin or ahora
        tiempo = max(0, round((fin - turno.fecha_entrada_cola).total_seconds() / 60))
    return {
        'id': turno.id,
        'numero': turno.numero_turno,
        'estado': turno.estado,
        'tipo_prioridad': turno.tipo_prioridad,
        'area_id': turno.area_id,
        'doctor': turno.doctor.nombre if turno.doctor else None,
        'doctor_id': turno.doctor_id,
        'servicio': turno.servicio.nombre if turno.servicio else None,
        'servicios': [{'nombre': s.servicio.nombre if s.servicio else 'Servicio', 'estado': s.estado}
                      for s in servicios],
        'atencion': {'id': atencion.id, 'folio': atencion.folio,
                     'paciente': atencion.nombre_paciente, 'estado': atencion.estado},
        'fecha_entrada': _fecha_utc(turno.fecha_entrada_cola),
        'fecha_llamado': _fecha_utc(turno.fecha_llamado),
        'fecha_inicio': _fecha_utc(turno.fecha_inicio),
        'fecha_fin': _fecha_utc(turno.fecha_fin),
        'minutos_en_area': tiempo,
    }


@bp_panel_medicos.get('/medicos')
def pagina_medicos():
    if not current_user.is_authenticated:
        return redirect(url_for('login_page'))
    if not operador_tiene_area_medica(current_user):
        abort(403)
    return render_template('medicos.html')


@bp_panel_medicos.get('/api/medicos/panel')
def datos_panel_medicos():
    areas = _autorizar_api()
    if not isinstance(areas, list):
        return areas
    area = _area_elegida(areas)
    if area is None:
        return jsonify(success=False, error='Área médica no autorizada'), 403

    ahora = datetime.utcnow()
    inicio_hoy = _inicio_jornada_utc()
    activos = (
        TurnoArea.query
        .join(Atencion, Atencion.id == TurnoArea.atencion_id)
        .options(
            selectinload(TurnoArea.atencion).selectinload(Atencion.servicios).selectinload(AtencionServicio.servicio),
            selectinload(TurnoArea.doctor),
            selectinload(TurnoArea.servicio),
        )
        .filter(
            TurnoArea.area_id == area.id,
            TurnoArea.doctor_id == current_user.doctor_id,
            Atencion.sede_id == current_user.sede_id,
            TurnoArea.estado.in_(ESTADOS_ACTIVOS),
        )
        .order_by(TurnoArea.fecha_entrada_cola.asc(), TurnoArea.id.asc())
        .limit(300).all()
    )
    historial = (
        TurnoArea.query
        .join(Atencion, Atencion.id == TurnoArea.atencion_id)
        .options(
            selectinload(TurnoArea.atencion).selectinload(Atencion.servicios).selectinload(AtencionServicio.servicio),
            selectinload(TurnoArea.doctor),
            selectinload(TurnoArea.servicio),
        )
        .filter(
            TurnoArea.area_id == area.id,
            TurnoArea.doctor_id == current_user.doctor_id,
            Atencion.sede_id == current_user.sede_id,
            TurnoArea.estado.in_(ESTADOS_HISTORICOS),
            TurnoArea.fecha_fin >= inicio_hoy,
        )
        .order_by(TurnoArea.fecha_fin.desc(), TurnoArea.id.desc())
        .limit(40).all()
    )
    # Conteo real, aunque la lista esté limitada a 300 turnos.
    conteos = dict(
        db.session.query(TurnoArea.estado, func.count(TurnoArea.id))
        .join(Atencion, Atencion.id == TurnoArea.atencion_id)
        .filter(
            TurnoArea.area_id == area.id,
            TurnoArea.doctor_id == current_user.doctor_id,
            Atencion.sede_id == current_user.sede_id,
            TurnoArea.estado.in_(ESTADOS_ACTIVOS),
        )
        .group_by(TurnoArea.estado).all()
    )
    finalizados_hoy = (
        db.session.query(func.count(TurnoArea.id))
        .join(Atencion, Atencion.id == TurnoArea.atencion_id)
        .filter(
            TurnoArea.area_id == area.id,
            TurnoArea.doctor_id == current_user.doctor_id,
            Atencion.sede_id == current_user.sede_id,
            TurnoArea.estado == 'FINALIZADO',
            TurnoArea.fecha_fin >= inicio_hoy,
        ).scalar() or 0
    )
    return jsonify({
        'success': True,
        'operador': {'nombre': current_user.nombre, 'usuario': current_user.usuario, 'rol': current_user.rol},
        'medico': {'id': current_user.doctor_id, 'nombre': current_user.doctor.nombre},
        'consultorios': _consultorios_asignados(current_user, area.id),
        'sede_id': current_user.sede_id,
        'sede_nombre': current_user.sede.nombre if current_user.sede else f'Sede #{current_user.sede_id}',
        'areas': [{'id': a.id, 'nombre': a.nombre, 'codigo': a.codigo} for a in areas],
        'area_actual': {'id': area.id, 'nombre': area.nombre, 'codigo': area.codigo},
        'conteos': {s: conteos.get(s, 0) for s in ESTADOS_ACTIVOS},
        'finalizados_hoy': finalizados_hoy,
        'total_activos': sum(conteos.values()),
        'limite_listado': 300,
        'turnos': [_turno_dict(t, ahora) for t in activos],
        'historial_hoy': [_turno_dict(t, ahora) for t in historial],
        'acciones': {p: verificar_permiso(p) for p in (
            'turnos_llamar', 'turnos_iniciar', 'turnos_omitir',
            'turnos_pausar', 'turnos_reanudar',
        )},
        'actualizado': _fecha_utc(ahora),
        'alcance': 'MEDICO_INDIVIDUAL',
    })


@bp_panel_medicos.get('/api/medicos/panel/turnos/<int:turno_id>')
def detalle_turno_medico(turno_id):
    areas = _autorizar_api()
    if not isinstance(areas, list):
        return areas
    turno = (
        TurnoArea.query.join(Atencion, Atencion.id == TurnoArea.atencion_id)
        .options(
            selectinload(TurnoArea.atencion).selectinload(Atencion.servicios).selectinload(AtencionServicio.servicio),
            selectinload(TurnoArea.doctor), selectinload(TurnoArea.servicio),
        )
        .filter(
            TurnoArea.id == turno_id,
            TurnoArea.area_id.in_([a.id for a in areas]),
            TurnoArea.doctor_id == current_user.doctor_id,
            Atencion.sede_id == current_user.sede_id,
        ).first()
    )
    if turno is None:
        return jsonify(success=False, error='Turno no asignado al médico autenticado'), 404
    historial = (
        HistorialTurno.query.filter_by(turno_area_id=turno.id)
        .order_by(HistorialTurno.fecha_hora.desc(), HistorialTurno.id.desc())
        .limit(25).all()
    )
    return jsonify({
        'success': True,
        'turno': _turno_dict(turno, datetime.utcnow()),
        'historial': [{
            'fecha': _fecha_utc(h.fecha_hora), 'accion': h.accion,
            'estado_anterior': h.estado_anterior, 'estado_nuevo': h.estado_nuevo,
            'motivo': h.motivo,
        } for h in historial],
    })
