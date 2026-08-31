from datetime import datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from app import db
from app.models import (
    Doctor,
    Paciente,
    Atencion,
    TurnoArea,
    Area,
    Servicio,
    HistorialTurno,
    Cita
)


bp = Blueprint('api', __name__, url_prefix='/api')


# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def generar_temporal():
    """
    Genera un identificador temporal con máximo 30 caracteres.
    TMP- = 4
    UUID recortado = 26
    Total = 30
    """
    return f'TMP-{uuid4().hex[:26]}'


def serializar_atencion(atencion):
    return {
        'id': atencion.id,
        'folio': atencion.folio,
        'paciente_id': atencion.paciente_id,
        'paciente_nombre': atencion.nombre_paciente,
        'tipo': atencion.tipo_llegada,
        'afiliado': atencion.afiliado_al_llegar,
        'estado': atencion.estado,
        'cita_id': atencion.cita_id,
        'servicio_inicial_id': atencion.servicio_inicial_id,
        'doctor_solicitado_id': atencion.doctor_solicitado_id,

        'hora_llegada': (
            atencion.fecha_hora_llegada.isoformat()
            if atencion.fecha_hora_llegada
            else None
        ),

        'hora_salida': (
            atencion.fecha_hora_fin.isoformat()
            if atencion.fecha_hora_fin
            else None
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
            if turno.atencion
            else None
        ),

        'tipo': (
            turno.atencion.tipo_llegada
            if turno.atencion
            else None
        ),

        'area_id': turno.area_id,

        'area': (
            turno.area.nombre
            if turno.area
            else None
        ),

        'servicio_id': turno.servicio_id,

        'servicio': (
            turno.servicio.nombre
            if turno.servicio
            else None
        ),

        'doctor_id': turno.doctor_id,

        'doctor': (
            turno.doctor.nombre
            if turno.doctor
            else None
        ),

        'estado': turno.estado,
        'tipo_prioridad': turno.tipo_prioridad,

        'fecha_entrada_cola': (
            turno.fecha_entrada_cola.isoformat()
            if turno.fecha_entrada_cola
            else None
        ),

        'fecha_llamado': (
            turno.fecha_llamado.isoformat()
            if turno.fecha_llamado
            else None
        ),

        'fecha_inicio': (
            turno.fecha_inicio.isoformat()
            if turno.fecha_inicio
            else None
        ),

        'fecha_fin': (
            turno.fecha_fin.isoformat()
            if turno.fecha_fin
            else None
        ),

        'veces_omitido': turno.veces_omitido
    }


def nombre_completo_paciente(paciente):
    partes = [
        paciente.nombre,
        paciente.apellido_paterno,
        paciente.apellido_materno
    ]

    return ' '.join(
        parte.strip()
        for parte in partes
        if parte and parte.strip()
    )


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
            'buscar_paciente': '/api/control/buscar-paciente?q=nombre',
            'registrar_control': '/api/control/registrar',
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
# CONTROL / RECEPCIÓN INICIAL
# =====================================================

@bp.route('/control/buscar-paciente', methods=['GET'])
def buscar_paciente_control():
    try:
        termino = (
            request.args.get('q')
            or ''
        ).strip()

        if len(termino) < 2:
            return jsonify({
                'success': True,
                'pacientes': [],
                'total': 0
            })

        patron = f'%{termino}%'

        pacientes = (
            Paciente.query
            .filter(
                Paciente.activo.is_(True),
                or_(
                    Paciente.nombre.ilike(patron),
                    Paciente.apellido_paterno.ilike(patron),
                    Paciente.apellido_materno.ilike(patron),
                    Paciente.numero_afiliacion.ilike(patron)
                )
            )
            .order_by(
                Paciente.apellido_paterno,
                Paciente.apellido_materno,
                Paciente.nombre
            )
            .limit(20)
            .all()
        )

        resultado = []

        for paciente in pacientes:
            resultado.append({
                'id': paciente.id,
                'nombre': paciente.nombre,
                'apellido_paterno': paciente.apellido_paterno,
                'apellido_materno': paciente.apellido_materno,
                'nombre_completo': nombre_completo_paciente(
                    paciente
                ),
                'numero_afiliacion': paciente.numero_afiliacion,
                'afiliado': paciente.afiliado,
                'telefono': paciente.telefono,

                'fecha_nacimiento': (
                    paciente.fecha_nacimiento.isoformat()
                    if paciente.fecha_nacimiento
                    else None
                ),

                'activo': paciente.activo
            })

        return jsonify({
            'success': True,
            'pacientes': resultado,
            'total': len(resultado)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/control/registrar', methods=['POST'])
def registrar_control():
    try:
        data = request.get_json(
            silent=True
        ) or {}

        # =================================================
        # DATOS BÁSICOS
        # =================================================

        paciente_id = data.get(
            'paciente_id'
        )

        nombre = (
            data.get('nombre')
            or data.get('nombre_paciente')
            or ''
        ).strip()

        apellido_paterno = (
            data.get('apellido_paterno')
            or ''
        ).strip() or None

        apellido_materno = (
            data.get('apellido_materno')
            or ''
        ).strip() or None

        telefono = (
            data.get('telefono')
            or ''
        ).strip() or None

        numero_afiliacion = (
            data.get('numero_afiliacion')
            or ''
        ).strip() or None

        afiliado = bool(
            data.get(
                'afiliado',
                False
            )
        )

        tipo_llegada = str(
            data.get(
                'tipo_llegada',
                data.get(
                    'tipo',
                    'SIN_CITA'
                )
            )
        ).strip().upper()

        servicio_id = data.get(
            'servicio_id'
        )

        doctor_id = data.get(
            'doctor_id'
        )

        cita_id = data.get(
            'cita_id'
        )

        observaciones = data.get(
            'observaciones'
        )

        usuario = (
            data.get('usuario')
            or data.get('creado_por')
            or 'control'
        )

        # =================================================
        # VALIDAR TIPO DE LLEGADA
        # =================================================

        if tipo_llegada not in (
            'CITA',
            'SIN_CITA'
        ):
            return jsonify({
                'success': False,
                'error': (
                    'tipo_llegada debe ser '
                    'CITA o SIN_CITA'
                )
            }), 400

        # =================================================
        # PACIENTE
        # =================================================

        paciente = None

        if paciente_id:
            try:
                paciente_id = int(
                    paciente_id
                )
            except (
                TypeError,
                ValueError
            ):
                return jsonify({
                    'success': False,
                    'error': (
                        'paciente_id no es válido'
                    )
                }), 400

            paciente = db.session.get(
                Paciente,
                paciente_id
            )

            if not paciente:
                return jsonify({
                    'success': False,
                    'error': (
                        'Paciente no encontrado'
                    )
                }), 404

        elif numero_afiliacion:
            paciente = (
                Paciente.query
                .filter_by(
                    numero_afiliacion=(
                        numero_afiliacion
                    )
                )
                .first()
            )

        if not paciente:
            if not nombre:
                return jsonify({
                    'success': False,
                    'error': (
                        'El nombre del paciente '
                        'es requerido'
                    )
                }), 400

            paciente = Paciente(
                nombre=nombre,
                apellido_paterno=apellido_paterno,
                apellido_materno=apellido_materno,
                telefono=telefono,
                numero_afiliacion=numero_afiliacion,
                afiliado=afiliado,
                activo=True
            )

            db.session.add(
                paciente
            )

            db.session.flush()

        else:
            if telefono:
                paciente.telefono = (
                    telefono
                )

            if numero_afiliacion:
                paciente.numero_afiliacion = (
                    numero_afiliacion
                )

            paciente.afiliado = (
                afiliado
            )

        # =================================================
        # NOMBRE SNAPSHOT
        # =================================================

        nombre_snapshot = (
            nombre_completo_paciente(
                paciente
            )
        )

        # =================================================
        # VALIDAR SERVICIO
        # =================================================

        servicio = None

        if servicio_id:
            try:
                servicio_id = int(
                    servicio_id
                )
            except (
                TypeError,
                ValueError
            ):
                return jsonify({
                    'success': False,
                    'error': (
                        'servicio_id no es válido'
                    )
                }), 400

            servicio = db.session.get(
                Servicio,
                servicio_id
            )

            if not servicio:
                return jsonify({
                    'success': False,
                    'error': (
                        'Servicio no encontrado'
                    )
                }), 404

            if not servicio.activo:
                return jsonify({
                    'success': False,
                    'error': (
                        'El servicio está inactivo'
                    )
                }), 400

        # =================================================
        # VALIDAR DOCTOR
        # =================================================

        doctor = None

        if doctor_id:
            try:
                doctor_id = int(
                    doctor_id
                )
            except (
                TypeError,
                ValueError
            ):
                return jsonify({
                    'success': False,
                    'error': (
                        'doctor_id no es válido'
                    )
                }), 400

            doctor = db.session.get(
                Doctor,
                doctor_id
            )

            if not doctor:
                return jsonify({
                    'success': False,
                    'error': (
                        'Doctor no encontrado'
                    )
                }), 404

        # =================================================
        # VALIDAR CITA
        # =================================================

        cita = None

        if cita_id:
            try:
                cita_id = int(
                    cita_id
                )
            except (
                TypeError,
                ValueError
            ):
                return jsonify({
                    'success': False,
                    'error': (
                        'cita_id no es válido'
                    )
                }), 400

            cita = db.session.get(
                Cita,
                cita_id
            )

            if not cita:
                return jsonify({
                    'success': False,
                    'error': (
                        'Cita no encontrada'
                    )
                }), 404

            tipo_llegada = (
                'CITA'
            )

        # =================================================
        # CREAR ATENCIÓN
        # =================================================

        atencion = Atencion(
            folio=generar_temporal(),

            paciente_id=paciente.id,

            cita_id=(
                cita.id
                if cita
                else None
            ),

            nombre_paciente=(
                nombre_snapshot
            ),

            tipo_llegada=(
                tipo_llegada
            ),

            afiliado_al_llegar=(
                afiliado
            ),

            servicio_inicial_id=(
                servicio.id
                if servicio
                else None
            ),

            doctor_solicitado_id=(
                doctor.id
                if doctor
                else None
            ),

            estado='ACTIVA',

            observaciones=(
                observaciones
            ),

            creado_por=usuario
        )

        db.session.add(
            atencion
        )

        db.session.flush()

        atencion.folio = (
            f'TV-{atencion.id:06d}'
        )

        # =================================================
        # DESTINO INICIAL
        # =================================================

        if afiliado:
            codigo_area_destino = (
                'CAJA'
            )
        else:
            codigo_area_destino = (
                'TRABAJO_SOCIAL'
            )

        area_destino = (
            Area.query
            .filter_by(
                codigo=(
                    codigo_area_destino
                ),
                activo=True
            )
            .first()
        )

        if not area_destino:
            db.session.rollback()

            return jsonify({
                'success': False,
                'error': (
                    f'No existe el área activa '
                    f'{codigo_area_destino}'
                )
            }), 500

        # =================================================
        # SERVICIO DE COLA
        # =================================================

        servicio_cola_id = None

        if not afiliado:
            servicio_afiliacion = (
                Servicio.query
                .filter_by(
                    codigo='AFILIACION',
                    activo=True
                )
                .first()
            )

            if servicio_afiliacion:
                servicio_cola_id = (
                    servicio_afiliacion.id
                )

        # =================================================
        # CREAR TURNO DE ÁREA
        # =================================================

        turno_area = TurnoArea(
            atencion_id=(
                atencion.id
            ),

            area_id=(
                area_destino.id
            ),

            servicio_id=(
                servicio_cola_id
            ),

            doctor_id=None,

            numero_turno=(
                generar_temporal()
            ),

            tipo_prioridad=(
                'CITA'
                if tipo_llegada == 'CITA'
                else 'NORMAL'
            ),

            estado='ESPERA'
        )

        db.session.add(
            turno_area
        )

        db.session.flush()

        prefijo = (
            area_destino.codigo[:3]
            .upper()
        )

        turno_area.numero_turno = (
            f'{prefijo}-'
            f'{turno_area.id:04d}'
        )

        # =================================================
        # HISTORIAL
        # =================================================

        historial_atencion = (
            HistorialTurno(
                atencion_id=(
                    atencion.id
                ),

                accion=(
                    'ATENCION_CREADA'
                ),

                estado_nuevo='ACTIVA',

                motivo=(
                    'Paciente registrado '
                    'en Recepción Inicial / Control'
                ),

                usuario=usuario
            )
        )

        historial_cola = (
            HistorialTurno(
                turno_area_id=(
                    turno_area.id
                ),

                atencion_id=(
                    atencion.id
                ),

                accion='ENTRADA_AREA',

                estado_nuevo='ESPERA',

                motivo=(
                    f'Paciente enviado a '
                    f'{area_destino.nombre}'
                ),

                usuario=usuario
            )
        )

        db.session.add(
            historial_atencion
        )

        db.session.add(
            historial_cola
        )

        # =================================================
        # CITA
        # =================================================

        if cita:
            cita.estado = (
                'PRESENTE'
            )

        # =================================================
        # GUARDAR
        # =================================================

        db.session.commit()

        return jsonify({
            'success': True,

            'message': (
                f'Paciente registrado. '
                f'Destino: '
                f'{area_destino.nombre}'
            ),

            'paciente': {
                'id': paciente.id,

                'nombre_completo': (
                    nombre_completo_paciente(
                        paciente
                    )
                ),

                'numero_afiliacion': (
                    paciente.numero_afiliacion
                ),

                'afiliado': (
                    paciente.afiliado
                )
            },

            'atencion': (
                serializar_atencion(
                    atencion
                )
            ),

            'destino': {
                'area_id': (
                    area_destino.id
                ),

                'codigo': (
                    area_destino.codigo
                ),

                'nombre': (
                    area_destino.nombre
                )
            },

            'turno_area': (
                serializar_turno_area(
                    turno_area
                )
            )
        }), 201

    except Exception as e:
        db.session.rollback()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =====================================================
# DOCTORES
# =====================================================

@bp.route('/doctores', methods=['GET'])
def get_doctores():
    try:
        doctores = (
            Doctor.query
            .order_by(
                Doctor.nombre
            )
            .all()
        )

        return jsonify({
            'success': True,

            'doctores': [
                doctor.to_dict()
                for doctor in doctores
            ],

            'total': len(
                doctores
            ),

            'timestamp': (
                datetime.now()
                .isoformat()
            )
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route(
    '/doctores/<int:doctor_id>',
    methods=['GET']
)
def get_doctor(doctor_id):
    doctor = db.session.get(
        Doctor,
        doctor_id
    )

    if not doctor:
        return jsonify({
            'success': False,
            'error': (
                'Doctor no encontrado'
            )
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
        doctor = db.session.get(
            Doctor,
            doctor_id
        )

        if not doctor:
            return jsonify({
                'success': False,
                'error': (
                    'Doctor no encontrado'
                )
            }), 404

        data = request.get_json(
            silent=True
        ) or {}

        if 'activo' in data:
            doctor.activo = bool(
                data['activo']
            )

        if 'disponible' in data:
            doctor.disponible = bool(
                data['disponible']
            )

        if 'estado' in data:
            doctor.estado = (
                data['estado']
            )

        if 'consultorio' in data:
            doctor.consultorio = (
                data['consultorio']
            )

        db.session.commit()

        return jsonify({
            'success': True,

            'message': (
                f'Doctor '
                f'{doctor.nombre} '
                f'actualizado'
            ),

            'doctor': (
                doctor.to_dict()
            )
        })

    except Exception as e:
        db.session.rollback()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route(
    '/doctores/estado',
    methods=['GET']
)
def get_estado_doctores():
    try:
        doctores = (
            Doctor.query
            .all()
        )

        total = len(
            doctores
        )

        activos = sum(
            1
            for doctor in doctores
            if doctor.activo
        )

        disponibles = sum(
            1
            for doctor in doctores
            if doctor.activo
            and doctor.disponible
        )

        ocupados = sum(
            1
            for doctor in doctores
            if doctor.activo
            and not doctor.disponible
        )

        inactivos = sum(
            1
            for doctor in doctores
            if not doctor.activo
        )

        return jsonify({
            'success': True,

            'doctores': [
                doctor.to_dict()
                for doctor in doctores
            ],

            'estadisticas': {
                'total': total,
                'activos': activos,
                'disponibles': (
                    disponibles
                ),
                'ocupados': ocupados,
                'inactivos': inactivos
            },

            'timestamp': (
                datetime.now()
                .isoformat()
            )
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route(
    '/doctores/dashboard',
    methods=['GET']
)
def dashboard_doctores():
    try:
        doctores = (
            Doctor.query
            .order_by(
                Doctor.nombre
            )
            .all()
        )

        resultado = []

        for doctor in doctores:
            resultado.append({
                'id': doctor.id,
                'nombre': doctor.nombre,
                'especialidad': (
                    doctor.especialidad
                ),
                'activo': doctor.activo,
                'disponible': (
                    doctor.disponible
                ),
                'estatus': doctor.estado,
                'estado': doctor.estado,
                'consultorio': (
                    doctor.consultorio
                ),
                'consultorio_numero': (
                    doctor.consultorio
                ),
                'enfermero_nombre': None
            })

        total = len(
            doctores
        )

        activos = sum(
            1
            for doctor in doctores
            if doctor.activo
        )

        disponibles = sum(
            1
            for doctor in doctores
            if doctor.activo
            and doctor.disponible
        )

        ocupados = sum(
            1
            for doctor in doctores
            if doctor.activo
            and not doctor.disponible
        )

        return jsonify({
            'success': True,

            'doctores': (
                resultado
            ),

            'estadisticas': {
                'total': total,
                'activos': activos,
                'disponibles': (
                    disponibles
                ),
                'ocupados': ocupados,
                'inactivos': (
                    total - activos
                )
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

@bp.route(
    '/areas',
    methods=['GET']
)
def get_areas():
    try:
        areas = (
            Area.query
            .order_by(
                Area.orden_visual
            )
            .all()
        )

        resultado = []

        for area in areas:
            resultado.append({
                'id': area.id,
                'codigo': area.codigo,
                'nombre': area.nombre,
                'descripcion': (
                    area.descripcion
                ),
                'genera_cola': (
                    area.genera_cola
                ),
                'activo': area.activo,
                'orden_visual': (
                    area.orden_visual
                )
            })

        return jsonify({
            'success': True,
            'areas': resultado,
            'total': len(
                resultado
            )
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =====================================================
# SERVICIOS
# =====================================================

@bp.route(
    '/servicios',
    methods=['GET']
)
def get_servicios():
    try:
        servicios = (
            Servicio.query
            .filter(
                Servicio.activo.is_(
                    True
                )
            )
            .order_by(
                Servicio.nombre
            )
            .all()
        )

        resultado = []

        for servicio in servicios:
            resultado.append({
                'id': servicio.id,
                'codigo': servicio.codigo,
                'nombre': servicio.nombre,
                'descripcion': (
                    servicio.descripcion
                ),
                'area_id': (
                    servicio.area_id
                ),

                'area': (
                    servicio.area.nombre
                    if servicio.area
                    else None
                ),

                'precio_base': (
                    float(
                        servicio.precio_base
                    )
                    if servicio.precio_base
                    is not None
                    else None
                ),

                'requiere_pago': (
                    servicio.requiere_pago
                ),

                'activo': (
                    servicio.activo
                )
            })

        return jsonify({
            'success': True,
            'servicios': resultado,
            'total': len(
                resultado
            )
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =====================================================
# ATENCIONES
# =====================================================

@bp.route(
    '/atenciones',
    methods=['GET']
)
def get_atenciones():
    try:
        atenciones = (
            Atencion.query
            .order_by(
                Atencion
                .fecha_hora_llegada
                .desc()
            )
            .all()
        )

        return jsonify({
            'success': True,

            'atenciones': [
                serializar_atencion(
                    atencion
                )
                for atencion
                in atenciones
            ],

            'total': len(
                atenciones
            )
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =====================================================
# TURNOS POR ÁREA
# =====================================================

@bp.route(
    '/turnos',
    methods=['GET']
)
def get_turnos():
    try:
        turnos = (
            TurnoArea.query
            .order_by(
                TurnoArea
                .fecha_entrada_cola
                .desc()
            )
            .all()
        )

        return jsonify({
            'success': True,

            'turnos': [
                serializar_turno_area(
                    turno
                )
                for turno
                in turnos
            ],

            'total': len(
                turnos
            )
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =====================================================
# REGISTRO TEMPORAL LEGACY
# =====================================================

@bp.route(
    '/turnos/nuevo',
    methods=['POST']
)
def crear_turno():
    try:
        data = request.get_json(
            silent=True
        ) or {}

        nombre = (
            data.get(
                'paciente_nombre'
            )
            or data.get(
                'nombre_paciente'
            )
        )

        if not nombre:
            return jsonify({
                'success': False,
                'error': (
                    'El nombre del paciente '
                    'es requerido'
                )
            }), 400

        tipo_llegada = (
            data.get(
                'tipo',
                data.get(
                    'tipo_llegada',
                    'SIN_CITA'
                )
            )
        )

        tipo_llegada = (
            str(
                tipo_llegada
            )
            .strip()
            .upper()
        )

        if tipo_llegada not in (
            'CITA',
            'SIN_CITA'
        ):
            return jsonify({
                'success': False,
                'error': (
                    'tipo_llegada debe ser '
                    'CITA o SIN_CITA'
                )
            }), 400

        servicio_id = data.get(
            'servicio_id'
        )

        doctor_id = data.get(
            'doctor_id'
        )

        servicio = None
        doctor = None

        if servicio_id:
            try:
                servicio_id = int(
                    servicio_id
                )
            except (
                TypeError,
                ValueError
            ):
                return jsonify({
                    'success': False,
                    'error': (
                        'servicio_id '
                        'no es válido'
                    )
                }), 400

            servicio = db.session.get(
                Servicio,
                servicio_id
            )

            if not servicio:
                return jsonify({
                    'success': False,
                    'error': (
                        'Servicio no encontrado'
                    )
                }), 404

        if doctor_id:
            try:
                doctor_id = int(
                    doctor_id
                )
            except (
                TypeError,
                ValueError
            ):
                return jsonify({
                    'success': False,
                    'error': (
                        'doctor_id '
                        'no es válido'
                    )
                }), 400

            doctor = db.session.get(
                Doctor,
                doctor_id
            )

            if not doctor:
                return jsonify({
                    'success': False,
                    'error': (
                        'Doctor no encontrado'
                    )
                }), 404

        atencion = Atencion(
            folio=generar_temporal(),

            nombre_paciente=(
                nombre.strip()
            ),

            tipo_llegada=(
                tipo_llegada
            ),

            afiliado_al_llegar=bool(
                data.get(
                    'afiliado',
                    False
                )
            ),

            servicio_inicial_id=(
                servicio.id
                if servicio
                else None
            ),

            doctor_solicitado_id=(
                doctor.id
                if doctor
                else None
            ),

            estado='ACTIVA',

            observaciones=(
                data.get(
                    'observaciones'
                )
            ),

            creado_por=(
                data.get(
                    'creado_por',
                    'recepcion'
                )
            )
        )

        db.session.add(
            atencion
        )

        db.session.flush()

        atencion.folio = (
            f'TV-{atencion.id:06d}'
        )

        historial = (
            HistorialTurno(
                atencion_id=(
                    atencion.id
                ),

                accion=(
                    'ATENCION_CREADA'
                ),

                estado_nuevo='ACTIVA',

                motivo=(
                    'Ingreso del paciente '
                    'al sistema'
                ),

                usuario=data.get(
                    'creado_por',
                    'recepcion'
                )
            )
        )

        db.session.add(
            historial
        )

        db.session.commit()

        return jsonify({
            'success': True,

            'message': (
                f'Atención '
                f'{atencion.folio} '
                f'creada'
            ),

            'atencion': (
                serializar_atencion(
                    atencion
                )
            ),

            'turno': (
                serializar_atencion(
                    atencion
                )
            )
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
    try:
        turno_actual = db.session.get(
            TurnoArea,
            turno_id
        )

        if not turno_actual:
            return jsonify({
                'success': False,
                'error': (
                    'Turno de área '
                    'no encontrado'
                )
            }), 404

        data = request.get_json(
            silent=True
        ) or {}

        area_destino_id = (
            data.get(
                'area_id'
            )
        )

        if not area_destino_id:
            return jsonify({
                'success': False,
                'error': (
                    'area_id es requerido'
                )
            }), 400

        try:
            area_destino_id = int(
                area_destino_id
            )

        except (
            TypeError,
            ValueError
        ):
            return jsonify({
                'success': False,
                'error': (
                    'area_id no es válido'
                )
            }), 400

        area_destino = db.session.get(
            Area,
            area_destino_id
        )

        if not area_destino:
            return jsonify({
                'success': False,
                'error': (
                    'Área destino '
                    'no encontrada'
                )
            }), 404

        ahora = datetime.utcnow()

        estado_anterior = (
            turno_actual.estado
        )

        turno_actual.estado = (
            'FINALIZADO'
        )

        turno_actual.fecha_fin = (
            ahora
        )

        servicio_id = data.get(
            'servicio_id'
        )

        if servicio_id:
            try:
                servicio_id = int(
                    servicio_id
                )

            except (
                TypeError,
                ValueError
            ):
                return jsonify({
                    'success': False,
                    'error': (
                        'servicio_id '
                        'no es válido'
                    )
                }), 400

            servicio = db.session.get(
                Servicio,
                servicio_id
            )

            if not servicio:
                return jsonify({
                    'success': False,
                    'error': (
                        'Servicio '
                        'no encontrado'
                    )
                }), 404

        doctor_id = data.get(
            'doctor_id'
        )

        if doctor_id:
            try:
                doctor_id = int(
                    doctor_id
                )

            except (
                TypeError,
                ValueError
            ):
                return jsonify({
                    'success': False,
                    'error': (
                        'doctor_id '
                        'no es válido'
                    )
                }), 400

            doctor = db.session.get(
                Doctor,
                doctor_id
            )

            if not doctor:
                return jsonify({
                    'success': False,
                    'error': (
                        'Doctor '
                        'no encontrado'
                    )
                }), 404

        nuevo_turno = TurnoArea(
            atencion_id=(
                turno_actual.atencion_id
            ),

            area_id=(
                area_destino.id
            ),

            servicio_id=(
                servicio_id
            ),

            doctor_id=(
                doctor_id
            ),

            numero_turno=(
                generar_temporal()
            ),

            tipo_prioridad=(
                data.get(
                    'tipo_prioridad',
                    'NORMAL'
                )
            ),

            estado='ESPERA'
        )

        db.session.add(
            nuevo_turno
        )

        db.session.flush()

        prefijo = (
            area_destino
            .codigo[:3]
            .upper()
            if area_destino.codigo
            else 'T'
        )

        nuevo_turno.numero_turno = (
            f'{prefijo}-'
            f'{nuevo_turno.id:04d}'
        )

        historial_salida = (
            HistorialTurno(
                turno_area_id=(
                    turno_actual.id
                ),

                atencion_id=(
                    turno_actual
                    .atencion_id
                ),

                accion='SALIDA_AREA',

                estado_anterior=(
                    estado_anterior
                ),

                estado_nuevo=(
                    'FINALIZADO'
                ),

                motivo=(
                    data.get(
                        'motivo'
                    )
                ),

                usuario=(
                    data.get(
                        'usuario',
                        'sistema'
                    )
                )
            )
        )

        historial_entrada = (
            HistorialTurno(
                turno_area_id=(
                    nuevo_turno.id
                ),

                atencion_id=(
                    nuevo_turno
                    .atencion_id
                ),

                accion='ENTRADA_AREA',

                estado_nuevo='ESPERA',

                motivo=(
                    f'Derivado a '
                    f'{area_destino.nombre}'
                ),

                usuario=(
                    data.get(
                        'usuario',
                        'sistema'
                    )
                )
            )
        )

        db.session.add(
            historial_salida
        )

        db.session.add(
            historial_entrada
        )

        db.session.commit()

        return jsonify({
            'success': True,

            'message': (
                f'Paciente enviado a '
                f'{area_destino.nombre}'
            ),

            'turno': (
                serializar_turno_area(
                    nuevo_turno
                )
            )
        })

    except Exception as e:
        db.session.rollback()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500