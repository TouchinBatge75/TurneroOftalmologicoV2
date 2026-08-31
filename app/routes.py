from flask import Blueprint, jsonify, request
from app import db
from app.models import (
    Doctor,
    Atencion,
    TurnoArea,
    Area,
    Servicio,
    HistorialTurno
)
from datetime import datetime
from uuid import uuid4


bp = Blueprint('api', __name__, url_prefix='/api')


# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def serializar_atencion(atencion):
    return {
        'id': atencion.id,
        'folio': atencion.folio,
        'paciente_nombre': atencion.nombre_paciente,
        'tipo': atencion.tipo_llegada,
        'afiliado': atencion.afiliado_al_llegar,
        'estado': atencion.estado,
        'servicio_inicial_id': atencion.servicio_inicial_id,
        'doctor_solicitado_id': atencion.doctor_solicitado_id,
        'hora_llegada': (
            atencion.fecha_hora_llegada.isoformat()
            if atencion.fecha_hora_llegada else None
        ),
        'hora_salida': (
            atencion.fecha_hora_fin.isoformat()
            if atencion.fecha_hora_fin else None
        ),
        'observaciones': atencion.observaciones
    }


def serializar_turno_area(turno):
    return {
        'id': turno.id,
        'numero': turno.numero_turno,
        'atencion_id': turno.atencion_id,

        'paciente_nombre': (
            turno.atencion.nombre_paciente
            if turno.atencion else None
        ),

        'tipo': (
            turno.atencion.tipo_llegada
            if turno.atencion else None
        ),

        'area_id': turno.area_id,

        'area': (
            turno.area.nombre
            if turno.area else None
        ),

        'servicio_id': turno.servicio_id,

        'servicio': (
            turno.servicio.nombre
            if turno.servicio else None
        ),

        'doctor_id': turno.doctor_id,

        'doctor': (
            turno.doctor.nombre
            if turno.doctor else None
        ),

        'estado': turno.estado,
        'tipo_prioridad': turno.tipo_prioridad,

        'fecha_entrada_cola': (
            turno.fecha_entrada_cola.isoformat()
            if turno.fecha_entrada_cola else None
        ),

        'fecha_llamado': (
            turno.fecha_llamado.isoformat()
            if turno.fecha_llamado else None
        ),

        'fecha_inicio': (
            turno.fecha_inicio.isoformat()
            if turno.fecha_inicio else None
        ),

        'fecha_fin': (
            turno.fecha_fin.isoformat()
            if turno.fecha_fin else None
        ),

        'veces_omitido': turno.veces_omitido
    }


# =====================================================
# API / PRUEBAS
# =====================================================

@bp.route('/')
def api_index():
    return jsonify({
        'app': 'Turnero Oftalmológico API',
        'version': '2.0',
        'status': 'running',
        'database': 'PostgreSQL',
        'endpoints': {
            'doctores': '/api/doctores',
            'atenciones': '/api/atenciones',
            'turnos': '/api/turnos',
            'areas': '/api/areas',
            'servicios': '/api/servicios',
            'test': '/api/test'
        }
    })


@bp.route('/test')
def test():
    return jsonify({
        'success': True,
        'message': 'API funcionando correctamente',
        'timestamp': datetime.now().isoformat()
    })


# =====================================================
# DOCTORES
# =====================================================

@bp.route('/doctores', methods=['GET'])
def get_doctores():
    try:
        doctores = Doctor.query.order_by(Doctor.nombre).all()

        return jsonify({
            'success': True,
            'doctores': [doctor.to_dict() for doctor in doctores],
            'total': len(doctores),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/doctores/<int:doctor_id>', methods=['GET'])
def get_doctor(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)

    if not doctor:
        return jsonify({
            'success': False,
            'error': 'Doctor no encontrado'
        }), 404

    return jsonify({
        'success': True,
        'doctor': doctor.to_dict()
    })


@bp.route(
    '/doctores/<int:doctor_id>/actualizar-estado',
    methods=['PUT']
)
def actualizar_estado_doctor(doctor_id):
    try:
        doctor = db.session.get(Doctor, doctor_id)

        if not doctor:
            return jsonify({
                'success': False,
                'error': 'Doctor no encontrado'
            }), 404

        data = request.get_json(silent=True) or {}

        if 'activo' in data:
            doctor.activo = bool(data['activo'])

        if 'disponible' in data:
            doctor.disponible = bool(data['disponible'])

        if 'estado' in data:
            doctor.estado = data['estado']

        if 'consultorio' in data:
            doctor.consultorio = data['consultorio']

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Doctor {doctor.nombre} actualizado',
            'doctor': doctor.to_dict()
        })

    except Exception as e:
        db.session.rollback()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/doctores/estado', methods=['GET'])
def get_estado_doctores():
    try:
        doctores = Doctor.query.all()

        total = len(doctores)
        activos = sum(1 for d in doctores if d.activo)

        disponibles = sum(
            1 for d in doctores
            if d.activo and d.disponible
        )

        ocupados = sum(
            1 for d in doctores
            if d.activo and not d.disponible
        )

        inactivos = sum(
            1 for d in doctores
            if not d.activo
        )

        return jsonify({
            'success': True,
            'doctores': [d.to_dict() for d in doctores],
            'estadisticas': {
                'total': total,
                'activos': activos,
                'disponibles': disponibles,
                'ocupados': ocupados,
                'inactivos': inactivos
            },
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/doctores/dashboard', methods=['GET'])
def dashboard_doctores():
    """
    Información resumida para el dashboard de recepción.
    """

    try:
        doctores = Doctor.query.order_by(Doctor.nombre).all()

        resultado = []

        for doctor in doctores:
            resultado.append({
                'id': doctor.id,
                'nombre': doctor.nombre,
                'especialidad': doctor.especialidad,
                'activo': doctor.activo,
                'disponible': doctor.disponible,
                'estatus': doctor.estado,
                'estado': doctor.estado,

                # Compatibilidad temporal con el HTML actual
                'consultorio': doctor.consultorio,
                'consultorio_numero': doctor.consultorio,

                # Enfermería tendrá su propio modelo posteriormente
                'enfermero_nombre': None
            })

        total = len(doctores)

        activos = sum(
            1 for d in doctores
            if d.activo
        )

        disponibles = sum(
            1 for d in doctores
            if d.activo and d.disponible
        )

        ocupados = sum(
            1 for d in doctores
            if d.activo and not d.disponible
        )

        return jsonify({
            'success': True,
            'doctores': resultado,
            'estadisticas': {
                'total': total,
                'activos': activos,
                'disponibles': disponibles,
                'ocupados': ocupados,
                'inactivos': total - activos
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =====================================================
# ÁREAS
# =====================================================

@bp.route('/areas', methods=['GET'])
def get_areas():
    try:
        areas = Area.query.order_by(Area.orden_visual).all()

        resultado = []

        for area in areas:
            resultado.append({
                'id': area.id,
                'codigo': area.codigo,
                'nombre': area.nombre,
                'descripcion': area.descripcion,
                'genera_cola': area.genera_cola,
                'activo': area.activo,
                'orden_visual': area.orden_visual
            })

        return jsonify({
            'success': True,
            'areas': resultado,
            'total': len(resultado)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =====================================================
# SERVICIOS
# =====================================================

@bp.route('/servicios', methods=['GET'])
def get_servicios():
    try:
        servicios = Servicio.query.order_by(
            Servicio.nombre
        ).all()

        resultado = []

        for servicio in servicios:
            resultado.append({
                'id': servicio.id,
                'codigo': servicio.codigo,
                'nombre': servicio.nombre,
                'descripcion': servicio.descripcion,
                'area_id': servicio.area_id,
                'area': (
                    servicio.area.nombre
                    if servicio.area else None
                ),
                'precio_base': (
                    float(servicio.precio_base)
                    if servicio.precio_base is not None
                    else None
                ),
                'requiere_pago': servicio.requiere_pago,
                'activo': servicio.activo
            })

        return jsonify({
            'success': True,
            'servicios': resultado,
            'total': len(resultado)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =====================================================
# ATENCIONES
#
# La atención es el "turno viajero".
# =====================================================

@bp.route('/atenciones', methods=['GET'])
def get_atenciones():
    try:
        atenciones = Atencion.query.order_by(
            Atencion.fecha_hora_llegada.desc()
        ).all()

        return jsonify({
            'success': True,
            'atenciones': [
                serializar_atencion(a)
                for a in atenciones
            ],
            'total': len(atenciones)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =====================================================
# /turnos
#
# Se conserva este endpoint por compatibilidad con
# el frontend actual.
#
# Ahora devuelve TURNOS DE ÁREA.
# =====================================================

@bp.route('/turnos', methods=['GET'])
def get_turnos():
    try:
        turnos = TurnoArea.query.order_by(
            TurnoArea.fecha_entrada_cola.desc()
        ).all()

        return jsonify({
            'success': True,
            'turnos': [
                serializar_turno_area(t)
                for t in turnos
            ],
            'total': len(turnos)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =====================================================
# REGISTRO DE LLEGADA
#
# Conservamos /turnos/nuevo temporalmente porque
# recepcion.html ya lo utiliza.
#
# Ahora crea una ATENCIÓN, no un turno de área.
# =====================================================

@bp.route('/turnos/nuevo', methods=['POST'])
def crear_turno():
    try:
        data = request.get_json(silent=True) or {}

        nombre = (
            data.get('paciente_nombre')
            or data.get('nombre_paciente')
        )

        if not nombre:
            return jsonify({
                'success': False,
                'error': 'El nombre del paciente es requerido'
            }), 400

        tipo_llegada = data.get(
            'tipo',
            data.get('tipo_llegada', 'SIN_CITA')
        )

        if tipo_llegada not in ('CITA', 'SIN_CITA'):
            return jsonify({
                'success': False,
                'error': 'tipo_llegada debe ser CITA o SIN_CITA'
            }), 400

        servicio_id = data.get('servicio_id')
        doctor_id = data.get('doctor_id')

        # Validar servicio
        servicio = None

        if servicio_id:
            servicio = db.session.get(
                Servicio,
                int(servicio_id)
            )

            if not servicio:
                return jsonify({
                    'success': False,
                    'error': 'Servicio no encontrado'
                }), 404

        # Validar doctor
        doctor = None

        if doctor_id:
            doctor = db.session.get(
                Doctor,
                int(doctor_id)
            )

            if not doctor:
                return jsonify({
                    'success': False,
                    'error': 'Doctor no encontrado'
                }), 404

        # Folio temporal para poder hacer flush
        folio_temporal = f'TMP-{uuid4().hex}'

        atencion = Atencion(
            folio=folio_temporal,
            nombre_paciente=nombre.strip(),
            tipo_llegada=tipo_llegada,
            afiliado_al_llegar=bool(
                data.get('afiliado', False)
            ),
            servicio_inicial_id=(
                servicio.id if servicio else None
            ),
            doctor_solicitado_id=(
                doctor.id if doctor else None
            ),
            estado='ACTIVA',
            observaciones=data.get('observaciones'),
            creado_por=data.get(
                'creado_por',
                'recepcion'
            )
        )

        db.session.add(atencion)

        # Obtiene el ID sin terminar todavía la transacción
        db.session.flush()

        # Folio viajero definitivo
        atencion.folio = f'TV-{atencion.id:06d}'

        historial = HistorialTurno(
            atencion_id=atencion.id,
            accion='ATENCION_CREADA',
            estado_nuevo='ACTIVA',
            motivo='Ingreso del paciente al sistema',
            usuario=data.get(
                'creado_por',
                'recepcion'
            )
        )

        db.session.add(historial)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                f'Atención {atencion.folio} creada'
            ),
            'atencion': serializar_atencion(atencion),

            # Compatibilidad temporal
            'turno': serializar_atencion(atencion)
        }), 201

    except Exception as e:
        db.session.rollback()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =====================================================
# MOVER / DERIVAR A OTRA ÁREA
# =====================================================

@bp.route(
    '/turnos/<int:turno_id>/mover',
    methods=['POST']
)
def mover_turno(turno_id):
    """
    Finaliza el turno de área actual y crea una nueva
    entrada en la cola del área destino.
    """

    try:
        turno_actual = db.session.get(
            TurnoArea,
            turno_id
        )

        if not turno_actual:
            return jsonify({
                'success': False,
                'error': 'Turno de área no encontrado'
            }), 404

        data = request.get_json(silent=True) or {}

        area_destino_id = data.get('area_id')

        if not area_destino_id:
            return jsonify({
                'success': False,
                'error': 'area_id es requerido'
            }), 400

        area_destino = db.session.get(
            Area,
            int(area_destino_id)
        )

        if not area_destino:
            return jsonify({
                'success': False,
                'error': 'Área destino no encontrada'
            }), 404

        ahora = datetime.utcnow()

        # Cerrar turno actual
        estado_anterior = turno_actual.estado

        turno_actual.estado = 'FINALIZADO'
        turno_actual.fecha_fin = ahora

        # Nuevo turno
        nuevo_turno = TurnoArea(
            atencion_id=turno_actual.atencion_id,
            area_id=area_destino.id,
            servicio_id=data.get('servicio_id'),
            doctor_id=data.get('doctor_id'),
            numero_turno=f'TMP-{uuid4().hex}',
            tipo_prioridad=data.get(
                'tipo_prioridad',
                'NORMAL'
            ),
            estado='ESPERA'
        )

        db.session.add(nuevo_turno)
        db.session.flush()

        prefijo = (
            area_destino.codigo[:3].upper()
            if area_destino.codigo
            else 'T'
        )

        nuevo_turno.numero_turno = (
            f'{prefijo}-{nuevo_turno.id:04d}'
        )

        # Historial: salida
        historial_salida = HistorialTurno(
            turno_area_id=turno_actual.id,
            atencion_id=turno_actual.atencion_id,
            accion='SALIDA_AREA',
            estado_anterior=estado_anterior,
            estado_nuevo='FINALIZADO',
            motivo=data.get('motivo'),
            usuario=data.get(
                'usuario',
                'sistema'
            )
        )

        # Historial: entrada
        historial_entrada = HistorialTurno(
            turno_area_id=nuevo_turno.id,
            atencion_id=nuevo_turno.atencion_id,
            accion='ENTRADA_AREA',
            estado_nuevo='ESPERA',
            motivo=(
                f'Derivado a {area_destino.nombre}'
            ),
            usuario=data.get(
                'usuario',
                'sistema'
            )
        )

        db.session.add(historial_salida)
        db.session.add(historial_entrada)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                f'Paciente enviado a '
                f'{area_destino.nombre}'
            ),
            'turno': serializar_turno_area(
                nuevo_turno
            )
        })

    except Exception as e:
        db.session.rollback()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500