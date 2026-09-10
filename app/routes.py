from datetime import datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import or_, and_

from app import db
from app.models import (
    Doctor,
    Paciente,
    Atencion,
    AtencionServicio,
    TurnoArea,
    Area,
    Servicio,
    ServicioSede,
    HistorialTurno,
    Cita,
    Sede,
    SedeArea
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

        'sede_id': atencion.sede_id,

        'sede': (
            {
                'id': atencion.sede.id,
                'codigo': atencion.sede.codigo,
                'nombre': atencion.sede.nombre
            }
            if atencion.sede
            else None
        ),

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
    atencion = turno.atencion

    return {
        'id': turno.id,
        'numero': turno.numero_turno,
        'atencion_id': turno.atencion_id,

        'sede_id': (
            atencion.sede_id
            if atencion
            else None
        ),

        'sede': (
            {
                'id': atencion.sede.id,
                'codigo': atencion.sede.codigo,
                'nombre': atencion.sede.nombre
            }
            if atencion and atencion.sede
            else None
        ),

        'paciente_nombre': (
            atencion.nombre_paciente
            if atencion
            else None
        ),

        'tipo': (
            atencion.tipo_llegada
            if atencion
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


def obtener_sede_desde_query():
    sede_id = request.args.get(
        'sede_id'
    )

    if not sede_id:
        return None, (
            jsonify({
                'success': False,
                'error': 'sede_id es requerido'
            }),
            400
        )

    try:
        sede_id = int(
            sede_id
        )

    except (
        TypeError,
        ValueError
    ):
        return None, (
            jsonify({
                'success': False,
                'error': 'sede_id no es válido'
            }),
            400
        )

    sede = db.session.get(
        Sede,
        sede_id
    )

    if not sede:
        return None, (
            jsonify({
                'success': False,
                'error': 'Sede no encontrada'
            }),
            404
        )

    if not sede.activo:
        return None, (
            jsonify({
                'success': False,
                'error': 'La sede está inactiva'
            }),
            400
        )

    return sede, None
def area_disponible_en_sede(sede_id, area_id):
    """
    Indica si un área está disponible para operar
    dentro de una sede específica.

    Se consideran dos niveles:
    1. El área debe estar activa globalmente.
    2. La relación SedeArea debe estar activa.
    """

    sede_area = (
        SedeArea.query
        .join(
            Area,
            SedeArea.area_id == Area.id
        )
        .filter(
            SedeArea.sede_id == sede_id,
            SedeArea.area_id == area_id,
            SedeArea.activo.is_(True),
            Area.activo.is_(True)
        )
        .first()
    )

    return sede_area is not None

def obtener_servicio_en_sede(sede_id, servicio_id):
    """
    Obtiene la configuración de un servicio
    dentro de una sede.

    Para que sea utilizable:
    1. El servicio debe estar activo globalmente.
    2. Su área debe estar activa globalmente.
    3. El área debe estar habilitada en la sede.
    4. El servicio debe estar disponible en la sede.
    """

    servicio_sede = (
        ServicioSede.query
        .join(
            Servicio,
            ServicioSede.servicio_id == Servicio.id
        )
        .join(
            Area,
            Servicio.area_id == Area.id
        )
        .join(
            SedeArea,
            and_(
                SedeArea.sede_id == ServicioSede.sede_id,
                SedeArea.area_id == Servicio.area_id
            )
        )
        .filter(
            ServicioSede.sede_id == sede_id,
            ServicioSede.servicio_id == servicio_id,
            ServicioSede.disponible.is_(True),
            Servicio.activo.is_(True),
            Area.activo.is_(True),
            SedeArea.activo.is_(True)
        )
        .first()
    )

    return servicio_sede

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
            'sedes': '/api/sedes',
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


@bp.route('/sedes', methods=['GET'])
def get_sedes():
    try:
        sedes = (
            Sede.query
            .filter(
                Sede.activo.is_(True)
            )
            .order_by(
                Sede.nombre.asc()
            )
            .all()
        )

        return jsonify({
            'success': True,
            'sedes': [
                sede.to_dict()
                for sede in sedes
            ],
            'total': len(sedes)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
@bp.route('/sedes/<int:sede_id>/areas', methods=['GET'])
def get_areas_sede(sede_id):
    try:
        # =============================================
        # 1. BUSCAR SEDE
        # =============================================

        sede = db.session.get(
            Sede,
            sede_id
        )

        if not sede:
            return jsonify({
                'success': False,
                'error': 'Sede no encontrada'
            }), 404

        # =============================================
        # 2. BUSCAR TODAS LAS ÁREAS DE LA SEDE
        # =============================================

        areas_sede = (
            SedeArea.query
            .join(
                Area,
                SedeArea.area_id == Area.id
            )
            .filter(
                SedeArea.sede_id == sede.id
            )
            .order_by(
                SedeArea.orden_visual.asc(),
                Area.nombre.asc()
            )
            .all()
        )

        # =============================================
        # 3. RESPUESTA
        # =============================================

        return jsonify({
            'success': True,

            'sede': sede.to_dict(),

            'areas': [
                sede_area.to_dict()
                for sede_area in areas_sede
            ],

            'total': len(areas_sede)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route(
    '/sedes/<int:sede_id>/servicios',
    methods=['GET']
)
def get_servicios_sede(sede_id):
    try:
        # =============================================
        # 1. VALIDAR SEDE
        # =============================================

        sede = db.session.get(
            Sede,
            sede_id
        )

        if not sede:
            return jsonify({
                'success': False,
                'error': 'Sede no encontrada'
            }), 404

        # =============================================
        # 2. BUSCAR SERVICIOS CONFIGURADOS EN LA SEDE
        # =============================================

        servicios_sede = (
            ServicioSede.query
            .join(
                Servicio,
                ServicioSede.servicio_id == Servicio.id
            )
            .join(
                Area,
                Servicio.area_id == Area.id
            )
            .filter(
                ServicioSede.sede_id == sede.id
            )
            .order_by(
                Area.orden_visual.asc(),
                Servicio.nombre.asc()
            )
            .all()
        )

        # =============================================
        # 3. RESPUESTA
        # =============================================

        return jsonify({
            'success': True,

            'sede': sede.to_dict(),

            'servicios': [
                servicio_sede.to_dict()
                for servicio_sede in servicios_sede
            ],

            'total': len(
                servicios_sede
            )
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route(
    '/sedes/<int:sede_id>/servicios/<int:servicio_id>',
    methods=['PUT']
)
def actualizar_servicio_sede(sede_id, servicio_id):
    try:
        # =============================================
        # 1. VALIDAR SEDE
        # =============================================

        sede = db.session.get(
            Sede,
            sede_id
        )

        if not sede:
            return jsonify({
                'success': False,
                'error': 'Sede no encontrada'
            }), 404

        # =============================================
        # 2. VALIDAR SERVICIO
        # =============================================

        servicio = db.session.get(
            Servicio,
            servicio_id
        )

        if not servicio:
            return jsonify({
                'success': False,
                'error': 'Servicio no encontrado'
            }), 404

        # =============================================
        # 3. BUSCAR CONFIGURACIÓN SEDE - SERVICIO
        # =============================================

        servicio_sede = (
            ServicioSede.query
            .filter_by(
                sede_id=sede.id,
                servicio_id=servicio.id
            )
            .first()
        )

        if not servicio_sede:
            return jsonify({
                'success': False,
                'error': (
                    'El servicio no está configurado '
                    'para esta sede'
                )
            }), 404

        # =============================================
        # 4. LEER DATOS
        # =============================================

        data = request.get_json(
            silent=True
        ) or {}

        if (
            'disponible' not in data
            and 'modalidad' not in data
        ):
            return jsonify({
                'success': False,
                'error': (
                    'Debes enviar disponible '
                    'y/o modalidad'
                )
            }), 400

        # =============================================
        # 5. VALIDAR DISPONIBLE
        # =============================================

        nuevo_disponible = data.get(
            'disponible',
            servicio_sede.disponible
        )

        if not isinstance(
            nuevo_disponible,
            bool
        ):
            return jsonify({
                'success': False,
                'error': (
                    'disponible debe ser '
                    'true o false'
                )
            }), 400

        # =============================================
        # 6. VALIDAR MODALIDAD
        # =============================================

        nueva_modalidad = data.get(
            'modalidad',
            servicio_sede.modalidad
        )

        if nueva_modalidad is not None:
            if not isinstance(
                nueva_modalidad,
                str
            ):
                return jsonify({
                    'success': False,
                    'error': (
                        'modalidad debe ser '
                        'INTERNO, EXTERNO o null'
                    )
                }), 400

            nueva_modalidad = (
                nueva_modalidad
                .strip()
                .upper()
            )

        # Si el servicio queda deshabilitado,
        # no necesita modalidad.
        if not nuevo_disponible:
            nueva_modalidad = None

        # Si está disponible, sí debe tener modalidad.
        if (
            nuevo_disponible
            and nueva_modalidad not in (
                'INTERNO',
                'EXTERNO'
            )
        ):
            return jsonify({
                'success': False,
                'error': (
                    'Un servicio disponible debe tener '
                    'modalidad INTERNO o EXTERNO'
                )
            }), 400

        # =============================================
        # 7. ACTUALIZAR
        # =============================================

        servicio_sede.disponible = (
            nuevo_disponible
        )

        servicio_sede.modalidad = (
            nueva_modalidad
        )

        db.session.commit()

        # =============================================
        # 8. RESPUESTA
        # =============================================

        return jsonify({
            'success': True,

            'message': (
                f'Servicio {servicio.nombre} '
                f'actualizado en {sede.nombre}'
            ),

            'servicio_sede': (
                servicio_sede.to_dict()
            )
        })

    except Exception as e:
        db.session.rollback()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route(
    '/sedes/<int:sede_id>/areas/<int:area_id>',
    methods=['PUT']
)
def actualizar_area_sede(sede_id, area_id):
    try:
        # =============================================
        # 1. VALIDAR SEDE
        # =============================================

        sede = db.session.get(
            Sede,
            sede_id
        )

        if not sede:
            return jsonify({
                'success': False,
                'error': 'Sede no encontrada'
            }), 404

        # =============================================
        # 2. VALIDAR ÁREA
        # =============================================

        area = db.session.get(
            Area,
            area_id
        )

        if not area:
            return jsonify({
                'success': False,
                'error': 'Área no encontrada'
            }), 404

        # =============================================
        # 3. BUSCAR RELACIÓN SEDE - ÁREA
        # =============================================

        sede_area = (
            SedeArea.query
            .filter_by(
                sede_id=sede.id,
                area_id=area.id
            )
            .first()
        )

        if not sede_area:
            return jsonify({
                'success': False,
                'error': (
                    'El área no está configurada '
                    'para esta sede'
                )
            }), 404

        # =============================================
        # 4. LEER DATOS
        # =============================================

        data = request.get_json(
            silent=True
        ) or {}

        if 'activo' not in data:
            return jsonify({
                'success': False,
                'error': (
                    'El campo activo es requerido'
                )
            }), 400

        if not isinstance(data['activo'], bool):
            return jsonify({
                'success': False,
                'error': (
                    'activo debe ser true o false'
                )
            }), 400

        # =============================================
        # 5. ACTUALIZAR
        # =============================================

        sede_area.activo = data['activo']

        db.session.commit()

        # =============================================
        # 6. RESPUESTA
        # =============================================

        return jsonify({
            'success': True,
            'message': (
                f'Área {area.nombre} '
                f'actualizada en {sede.nombre}'
            ),
            'sede_area': sede_area.to_dict()
        })

    except Exception as e:
        db.session.rollback()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
        # VALIDAR SEDE
        # =================================================

        sede_id = data.get(
            'sede_id'
        )

        if not sede_id:
            return jsonify({
                'success': False,
                'error': 'sede_id es requerido'
            }), 400

        try:
            sede_id = int(
                sede_id
            )

        except (
            TypeError,
            ValueError
        ):
            return jsonify({
                'success': False,
                'error': 'sede_id no es válido'
            }), 400

        sede = db.session.get(
            Sede,
            sede_id
        )

        if not sede:
            return jsonify({
                'success': False,
                'error': 'Sede no encontrada'
            }), 404

        if not sede.activo:
            return jsonify({
                'success': False,
                'error': 'La sede está inactiva'
            }), 400

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

        afiliado_recibido = (
            'afiliado' in data
        )

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

        # Formato anterior: un solo servicio.
        servicio_id = data.get(
            'servicio_id'
        )

        # Formato nuevo: varios servicios.
        servicios_ids = data.get(
            'servicios_ids',
            []
        )

        if not isinstance(
            servicios_ids,
            list
        ):
            return jsonify({
                'success': False,
                'error': (
                    'servicios_ids debe ser '
                    'una lista'
                )
            }), 400

        # No modificamos directamente la lista que vino
        # en el JSON. Creamos una copia.
        servicios_ids = list(
            servicios_ids
        )

        # Compatibilidad con el formato anterior.
        if servicio_id is not None:
            servicios_ids.append(
                servicio_id
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

            # Solo modificamos la afiliación de un
            # paciente existente si vino explícitamente
            # en la petición.
            if afiliado_recibido:
                paciente.afiliado = (
                    afiliado
                )
            else:
                afiliado = bool(
                    paciente.afiliado
                )

        afiliado_actual = bool(
            paciente.afiliado
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
        # VALIDAR SERVICIOS
        # =================================================

        servicios = []
        servicios_vistos = set()
        configuraciones_servicios = {}

        for servicio_item_id in servicios_ids:
            try:
                servicio_item_id = int(
                    servicio_item_id
                )
            except (
                TypeError,
                ValueError
            ):
                return jsonify({
                    'success': False,
                    'error': (
                        'Uno de los servicio_id '
                        'no es válido'
                    )
                }), 400

            # Evitar duplicados, incluso si llegan como
            # 1 y "1".
            if servicio_item_id in servicios_vistos:
                continue

            servicios_vistos.add(
                servicio_item_id
            )

            servicio = db.session.get(
                Servicio,
                servicio_item_id
            )

            if not servicio:
                return jsonify({
                    'success': False,
                    'error': (
                        f'Servicio '
                        f'{servicio_item_id} '
                        f'no encontrado'
                    )
                }), 404

            configuracion_servicio = obtener_servicio_en_sede(
                sede.id,
                servicio.id
            )

            if not configuracion_servicio:
                return jsonify({
                    'success': False,
                    'error': (
                        f'El servicio {servicio.nombre} '
                        f'no está disponible en la sede '
                        f'{sede.nombre}'
                    )
                }), 409

            configuraciones_servicios[
                servicio.id
            ] = configuracion_servicio

            servicios.append(
                servicio
            )

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

            tipo_llegada = 'CITA'

        # =================================================
        # CREAR ATENCIÓN
        # =================================================

        atencion = Atencion(
            folio=generar_temporal(),

            sede_id=sede.id,

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
                afiliado_actual
            ),

            servicio_inicial_id=(
                servicios[0].id
                if servicios
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
        # REGISTRAR SERVICIOS SOLICITADOS
        # =================================================

        servicios_registrados = []

        for orden, servicio in enumerate(
            servicios,
            start=1
        ):
            atencion_servicio = AtencionServicio(
                atencion_id=atencion.id,
                servicio_id=servicio.id,
                origen='CONTROL',
                estado='PENDIENTE',

                modalidad=(
                    configuraciones_servicios[
                        servicio.id
                    ].modalidad
                ),

                requiere_pago=(
                    servicio.requiere_pago
                ),

                pagado=False,
                orden=orden
            )

            db.session.add(
                atencion_servicio
            )

            servicios_registrados.append({
                'servicio_id': servicio.id,
                'codigo': servicio.codigo,
                'nombre': servicio.nombre,
                 'modalidad': (
                    configuraciones_servicios[
                        servicio.id
                    ].modalidad
                ),
                'orden': orden,
                'pagado': False
            })

        # =================================================
        # DESTINO INICIAL
        # =================================================

        if afiliado_actual:
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
        # VALIDAR DESTINO EN LA SEDE
        # =================================================

        if not area_disponible_en_sede(
            sede.id,
            area_destino.id
        ):
            db.session.rollback()

            return jsonify({
                'success': False,
                'error': (
                    f'El área {area_destino.nombre} '
                    f'no está disponible en la sede '
                    f'{sede.nombre}'
                )
            }), 409

        # =================================================
        # SERVICIO DE COLA
        # =================================================

        servicio_cola_id = None

        if not afiliado_actual:
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

        historial_atencion = HistorialTurno(
            atencion_id=atencion.id,
            accion='ATENCION_CREADA',
            estado_nuevo='ACTIVA',
            motivo=(
                'Paciente registrado '
                'en Recepción Inicial / Control'
            ),
            usuario=usuario
        )

        historial_cola = HistorialTurno(
            turno_area_id=turno_area.id,
            atencion_id=atencion.id,
            accion='ENTRADA_AREA',
            estado_nuevo='ESPERA',
            motivo=(
                f'Paciente enviado a '
                f'{area_destino.nombre}'
            ),
            usuario=usuario
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

            'sede': {
                'id': sede.id,
                'codigo': sede.codigo,
                'nombre': sede.nombre
            },

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

            'servicios': (
                servicios_registrados
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

@bp.route(
    '/atencion-servicios/<int:atencion_servicio_id>/derivar-externo',
    methods=['POST']
)
def derivar_servicio_externo(atencion_servicio_id):
    try:
        # =============================================
        # 1. BUSCAR SERVICIO DE LA ATENCIÓN
        # =============================================

        atencion_servicio = db.session.get(
            AtencionServicio,
            atencion_servicio_id
        )

        if not atencion_servicio:
            return jsonify({
                'success': False,
                'error': (
                    'Servicio de atención '
                    'no encontrado'
                )
            }), 404

        # =============================================
        # 2. VALIDAR ATENCIÓN
        # =============================================

        atencion = atencion_servicio.atencion

        if not atencion:
            return jsonify({
                'success': False,
                'error': (
                    'La atención asociada '
                    'no fue encontrada'
                )
            }), 404

        # =============================================
        # 3. VALIDAR SERVICIO
        # =============================================

        servicio = atencion_servicio.servicio

        if not servicio:
            return jsonify({
                'success': False,
                'error': (
                    'El servicio asociado '
                    'no fue encontrado'
                )
            }), 404

        # =============================================
        # 4. VALIDAR MODALIDAD HISTÓRICA
        # =============================================

        if atencion_servicio.modalidad != 'EXTERNO':
            return jsonify({
                'success': False,
                'error': (
                    f'El servicio {servicio.nombre} '
                    f'no fue registrado como EXTERNO '
                    f'en esta atención'
                )
            }), 409

        # =============================================
        # 5. VALIDAR ESTADO
        # =============================================

        estados_permitidos = (
            'PENDIENTE',
            'DERIVADO_EXTERNO'
        )

        if (
            atencion_servicio.estado
            not in estados_permitidos
        ):
            return jsonify({
                'success': False,
                'error': (
                    f'El servicio no puede derivarse '
                    f'desde el estado '
                    f'{atencion_servicio.estado}'
                )
            }), 409

        ya_derivado = (
            atencion_servicio.estado
            == 'DERIVADO_EXTERNO'
        )

        # =============================================
        # 6. LEER DATOS OPCIONALES
        # =============================================

        if request.data:
            data = request.get_json(
                silent=True
            )

            if data is None:
                return jsonify({
                    'success': False,
                    'error': (
                        'El cuerpo JSON no es válido '
                        'o no pudo interpretarse correctamente'
                    )
                }), 400
        else:
            data = {}

        usuario = str(
            data.get('usuario')
            or 'sistema'
        ).strip()

        motivo = str(
            data.get('motivo')
            or ''
        ).strip()

        if not motivo:
            motivo = (
                f'Servicio {servicio.nombre} '
                f'derivado para realización externa'
            )

        # =============================================
        # 7. BUSCAR OTROS SERVICIOS PENDIENTES
        # =============================================

        otros_pendientes = (
            AtencionServicio.query
            .filter(
                AtencionServicio.atencion_id
                == atencion.id,

                AtencionServicio.id
                != atencion_servicio.id,

                AtencionServicio.estado
                == 'PENDIENTE'
            )
            .all()
        )

        quedan_servicios_pendientes = (
            len(otros_pendientes) > 0
        )

        # =============================================
        # 8. BUSCAR TURNO ACTIVO DE LA ATENCIÓN
        # =============================================

        turnos_activos = (
            TurnoArea.query
            .filter(
                TurnoArea.atencion_id
                == atencion.id,

                TurnoArea.estado.in_([
                    'ESPERA',
                    'LLAMADO',
                    'EN_ATENCION'
                ])
            )
            .order_by(
                TurnoArea.id.desc()
            )
            .all()
        )

        # Una atención normalmente debe tener
        # solamente un turno activo.
        if len(turnos_activos) > 1:
            return jsonify({
                'success': False,
                'error': (
                    'La atención tiene más de un '
                    'turno activo. Debe revisarse '
                    'antes de finalizarla.'
                )
            }), 409

        # =============================================
        # 9. MARCAR SERVICIO COMO DERIVADO
        # =============================================

        if not ya_derivado:
            estado_anterior = (
                atencion_servicio.estado
            )

            atencion_servicio.estado = (
                'DERIVADO_EXTERNO'
            )

            historial_servicio = HistorialTurno(
                turno_area_id=None,
                atencion_id=atencion.id,

                accion=(
                    'SERVICIO_DERIVADO_EXTERNO'
                ),

                estado_anterior=estado_anterior,

                estado_nuevo=(
                    'DERIVADO_EXTERNO'
                ),

                motivo=motivo,
                usuario=usuario
            )

            db.session.add(
                historial_servicio
            )

        # =============================================
        # 10. FINALIZAR RECORRIDO SI YA NO QUEDA NADA
        # =============================================

        atencion_finalizada = False
        turno_finalizado = None

        if not quedan_servicios_pendientes:
            ahora = datetime.utcnow()

            # -----------------------------------------
            # FINALIZAR TURNO ACTIVO
            # -----------------------------------------

            if turnos_activos:
                turno_actual = turnos_activos[0]

                estado_turno_anterior = (
                    turno_actual.estado
                )

                turno_actual.estado = (
                    'FINALIZADO'
                )

                turno_actual.fecha_fin = (
                    ahora
                )

                turno_finalizado = (
                    turno_actual
                )

                historial_salida = HistorialTurno(
                    turno_area_id=turno_actual.id,
                    atencion_id=atencion.id,

                    accion='SALIDA_AREA',

                    estado_anterior=(
                        estado_turno_anterior
                    ),

                    estado_nuevo='FINALIZADO',

                    motivo=(
                        'Fin del recorrido del '
                        'paciente en la fundación'
                    ),

                    usuario=usuario
                )

                db.session.add(
                    historial_salida
                )

            # -----------------------------------------
            # FINALIZAR ATENCIÓN
            # -----------------------------------------

            if atencion.estado != 'FINALIZADA':
                estado_atencion_anterior = (
                    atencion.estado
                )

                atencion.estado = (
                    'FINALIZADA'
                )

                atencion.fecha_hora_fin = (
                    ahora
                )

                historial_atencion = HistorialTurno(
                    turno_area_id=None,
                    atencion_id=atencion.id,

                    accion='ATENCION_FINALIZADA',

                    estado_anterior=(
                        estado_atencion_anterior
                    ),

                    estado_nuevo='FINALIZADA',

                    motivo=(
                        'Recorrido del paciente '
                        'finalizado'
                    ),

                    usuario=usuario
                )

                db.session.add(
                    historial_atencion
                )

            atencion_finalizada = True

        # =============================================
        # 11. GUARDAR
        # =============================================

        db.session.commit()

        # =============================================
        # 12. RESPUESTA
        # =============================================

        return jsonify({
            'success': True,

            'message': (
                f'Servicio {servicio.nombre} '
                f'derivado externamente'
                if not ya_derivado
                else (
                    f'El servicio {servicio.nombre} '
                    f'ya estaba derivado externamente'
                )
            ),

            'servicio': {
                'id': atencion_servicio.id,
                'atencion_id': atencion.id,
                'servicio_id': servicio.id,
                'codigo': servicio.codigo,
                'nombre': servicio.nombre,
                'modalidad': (
                    atencion_servicio.modalidad
                ),
                'estado': (
                    atencion_servicio.estado
                )
            },

            'quedan_servicios_pendientes': (
                quedan_servicios_pendientes
            ),

            'atencion_finalizada': (
                atencion_finalizada
            ),

            'atencion': {
                'id': atencion.id,
                'folio': atencion.folio,
                'estado': atencion.estado,

                'fecha_hora_fin': (
                    atencion.fecha_hora_fin.isoformat()
                    if atencion.fecha_hora_fin
                    else None
                )
            },

            'turno_finalizado': (
                {
                    'id': turno_finalizado.id,
                    'numero': (
                        turno_finalizado.numero_turno
                    ),
                    'estado': (
                        turno_finalizado.estado
                    )
                }
                if turno_finalizado
                else None
            )
        })

    except Exception as e:
        db.session.rollback()

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
        
@bp.route('/trabajo-social/turnos', methods=['GET'])
def trabajo_social_turnos():
    try:
        # =============================================
        # 1. VALIDAR SEDE
        # =============================================

        sede, error_sede = (
            obtener_sede_desde_query()
        )

        if error_sede:
            return error_sede

        # =============================================
        # 2. BUSCAR ÁREA DE TRABAJO SOCIAL
        # =============================================

        area = (
            Area.query
            .filter_by(
                codigo='TRABAJO_SOCIAL',
                activo=True
            )
            .first()
        )

        if not area:
            return jsonify({
                'success': False,
                'message': (
                    'No se encontró el área '
                    'de Trabajo Social'
                )
            }), 404

        # =============================================
        # 3. VALIDAR QUE TRABAJO SOCIAL OPERE EN LA SEDE
        # =============================================

        if not area_disponible_en_sede(
            sede.id,
            area.id
        ):
            return jsonify({
                'success': False,
                'error': (
                    f'El área Trabajo Social '
                    f'no está disponible en la sede '
                    f'{sede.nombre}'
                )
            }), 409

        # =============================================
        # 4. BUSCAR TURNOS DE ESTA SEDE
        # =============================================

        turnos = (
            TurnoArea.query
            .join(
                Atencion,
                TurnoArea.atencion_id
                == Atencion.id
            )
            .filter(
                TurnoArea.area_id
                == area.id,

                Atencion.sede_id
                == sede.id,

                TurnoArea.estado.in_([
                    'ESPERA',
                    'LLAMADO',
                    'EN_ATENCION'
                ])
            )
            .order_by(
                TurnoArea.prioridad_manual.desc(),
                TurnoArea.fecha_entrada_cola.asc()
            )
            .all()
        )

        resultado = []

        for turno in turnos:
            atencion = turno.atencion

            if not atencion:
                continue

            paciente = atencion.paciente

            resultado.append({
                'id': turno.id,
                'numero_turno': turno.numero_turno,
                'estado': turno.estado,
                'tipo_prioridad': turno.tipo_prioridad,
                'veces_omitido': turno.veces_omitido,

                'fecha_entrada_cola': (
                    turno.fecha_entrada_cola.isoformat()
                    if turno.fecha_entrada_cola
                    else None
                ),

                'atencion': {
                    'id': atencion.id,
                    'folio': atencion.folio,
                    'sede_id': atencion.sede_id,
                    'tipo_llegada': atencion.tipo_llegada,
                    'afiliado_al_llegar': (
                        atencion.afiliado_al_llegar
                    ),
                    'nombre_paciente': (
                        atencion.nombre_paciente
                    )
                },

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
                    'afiliado': paciente.afiliado,
                    'telefono': paciente.telefono
                } if paciente else None
            })

        return jsonify({
            'success': True,

            'sede': sede.to_dict(),

            'area': {
                'id': area.id,
                'codigo': area.codigo,
                'nombre': area.nombre
            },

            'total': len(resultado),
            'turnos': resultado
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': (
                'Error al consultar la cola '
                'de Trabajo Social'
            ),
            'error': str(e)
        }), 500

@bp.route(
    '/trabajo-social/<int:turno_id>/afiliar',
    methods=['POST']
)
def trabajo_social_afiliar(turno_id):
    try:
        # =============================================
        # 1. BUSCAR EL TURNO
        # =============================================

        turno = db.session.get(
            TurnoArea,
            turno_id
        )

        if not turno:
            return jsonify({
                'success': False,
                'error': 'Turno no encontrado'
            }), 404

        # =============================================
        # 2. COMPROBAR QUE ESTÁ EN TRABAJO SOCIAL
        # =============================================

        if not turno.area or turno.area.codigo != 'TRABAJO_SOCIAL':
            return jsonify({
                'success': False,
                'error': (
                    'El turno no pertenece '
                    'a Trabajo Social'
                )
            }), 400

        if turno.estado == 'FINALIZADO':
            return jsonify({
                'success': False,
                'error': 'El turno ya está finalizado'
            }), 400

        # =============================================
        # 3. OBTENER ATENCIÓN Y PACIENTE
        # =============================================

        atencion = turno.atencion

        if not atencion:
            return jsonify({
                'success': False,
                'error': 'La atención no fue encontrada'
            }), 404

        paciente = atencion.paciente

        if not paciente:
            return jsonify({
                'success': False,
                'error': 'El paciente no fue encontrado'
            }), 404

        # =============================================
        # 4. LEER LOS DATOS RECIBIDOS
        # =============================================

        data = request.get_json(
            silent=True
        ) or {}

        numero_afiliacion = (
            data.get('numero_afiliacion')
            or ''
        ).strip()

        usuario = (
            data.get('usuario')
            or 'trabajo_social'
        )

        if not numero_afiliacion:
            return jsonify({
                'success': False,
                'error': (
                    'El número de afiliación '
                    'es requerido'
                )
            }), 400

        # =============================================
        # 5. EVITAR NÚMEROS DUPLICADOS
        # =============================================

        paciente_existente = (
            Paciente.query
            .filter(
                Paciente.numero_afiliacion == numero_afiliacion,
                Paciente.id != paciente.id
            )
            .first()
        )

        if paciente_existente:
            return jsonify({
                'success': False,
                'error': (
                    'Ese número de afiliación '
                    'ya pertenece a otro paciente'
                )
            }), 409

        # =============================================
        # 6. BUSCAR CAJA
        # =============================================

        area_caja = (
            Area.query
            .filter_by(
                codigo='CAJA',
                activo=True
            )
            .first()
        )

        if not area_caja:
            return jsonify({
                'success': False,
                'error': (
                    'No existe un área de Caja activa'
                )
            }), 500
        # =============================================
        # 7. VALIDAR QUE CAJA OPERE EN ESTA SEDE
        # =============================================

        if not atencion.sede_id:
            return jsonify({
                'success': False,
                'error': (
                    'La atención no tiene una sede asignada'
                )
            }), 409

        if not area_disponible_en_sede(
            atencion.sede_id,
            area_caja.id
        ):
            return jsonify({
                'success': False,
                'error': (
                    'El área de Caja no está disponible '
                    'en esta sede'
                )
            }), 409

        # =============================================
        # 8. AFILIAR AL PACIENTE
        # =============================================

        paciente.afiliado = True
        paciente.numero_afiliacion = (
            numero_afiliacion
        )

        # IMPORTANTE:
        # NO modificamos atencion.afiliado_al_llegar.
        #
        # Ese campo conserva cómo llegó el paciente,
        # aunque sea afiliado posteriormente.

        ahora = datetime.utcnow()

        # =============================================
        # 9. FINALIZAR TRABAJO SOCIAL
        # =============================================

        estado_anterior = turno.estado

        turno.estado = 'FINALIZADO'
        turno.fecha_fin = ahora

        # =============================================
        # 10. CREAR NUEVO TURNO EN CAJA
        # =============================================

        nuevo_turno = TurnoArea(
            atencion_id=atencion.id,

            area_id=area_caja.id,

            servicio_id=None,

            doctor_id=None,

            numero_turno=generar_temporal(),

            tipo_prioridad=turno.tipo_prioridad,

            estado='ESPERA'
        )

        db.session.add(
            nuevo_turno
        )

        db.session.flush()

        nuevo_turno.numero_turno = (
            f'CAJ-{nuevo_turno.id:04d}'
        )

        # =============================================
        # 11. GUARDAR HISTORIAL
        # =============================================

        historial_afiliacion = HistorialTurno(
            atencion_id=atencion.id,

            accion='PACIENTE_AFILIADO',

            motivo=(
                f'Paciente afiliado con número '
                f'{numero_afiliacion}'
            ),

            usuario=usuario
        )

        historial_salida = HistorialTurno(
            turno_area_id=turno.id,

            atencion_id=atencion.id,

            accion='SALIDA_AREA',

            estado_anterior=estado_anterior,

            estado_nuevo='FINALIZADO',

            motivo=(
                'Afiliación completada '
                'en Trabajo Social'
            ),

            usuario=usuario
        )

        historial_entrada = HistorialTurno(
            turno_area_id=nuevo_turno.id,

            atencion_id=atencion.id,

            accion='ENTRADA_AREA',

            estado_nuevo='ESPERA',

            motivo='Paciente enviado a Caja',

            usuario=usuario
        )

        db.session.add(
            historial_afiliacion
        )

        db.session.add(
            historial_salida
        )

        db.session.add(
            historial_entrada
        )

        # =============================================
        # 12. GUARDAR TODO JUNTO
        # =============================================

        db.session.commit()

        return jsonify({
            'success': True,

            'message': (
                'Paciente afiliado y enviado a Caja'
            ),

            'paciente': {
                'id': paciente.id,
                'nombre_completo': (
                    nombre_completo_paciente(
                        paciente
                    )
                ),
                'afiliado': paciente.afiliado,
                'numero_afiliacion': (
                    paciente.numero_afiliacion
                )
            },

            'atencion': (
                serializar_atencion(
                    atencion
                )
            ),

            'turno_anterior': {
                'id': turno.id,
                'numero_turno': turno.numero_turno,
                'estado': turno.estado
            },

            'turno_caja': (
                serializar_turno_area(
                    nuevo_turno
                )
            )
        }), 200

    except Exception as e:
        db.session.rollback()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =====================================================
# CAJA
# =====================================================

@bp.route('/caja/turnos', methods=['GET'])
def caja_turnos():
    try:
        # =============================================
        # 1. VALIDAR SEDE
        # =============================================

        sede, error_sede = obtener_sede_desde_query()

        if error_sede:
            return error_sede

        # =============================================
        # 2. BUSCAR EL ÁREA DE CAJA
        # =============================================

        area_caja = (
            Area.query
            .filter_by(
                codigo='CAJA',
                activo=True
            )
            .first()
        )

        if not area_caja:
            return jsonify({
                'success': False,
                'error': 'No se encontró el área de Caja'
            }), 404

        # =============================================
        # 3. VALIDAR QUE CAJA OPERE EN ESTA SEDE
        # =============================================

        if not area_disponible_en_sede(
            sede.id,
            area_caja.id
        ):
            return jsonify({
                'success': False,
                'error': (
                    f'El área Caja no está disponible '
                    f'en la sede {sede.nombre}'
                )
            }), 409

        # =============================================
        # 4. BUSCAR TURNOS ACTIVOS DE ESTA SEDE
        # =============================================

        turnos = (
            TurnoArea.query
            .join(
                Atencion,
                TurnoArea.atencion_id == Atencion.id
            )
            .filter(
                TurnoArea.area_id == area_caja.id,

                Atencion.sede_id == sede.id,

                TurnoArea.estado.in_([
                    'ESPERA',
                    'LLAMADO',
                    'EN_ATENCION'
                ])
            )
            .order_by(
                TurnoArea.prioridad_manual.desc(),
                TurnoArea.fecha_entrada_cola.asc()
            )
            .all()
        )

        # =============================================
        # 5. PREPARAR RESPUESTA
        # =============================================

        resultado = []

        for turno in turnos:
            atencion = turno.atencion

            if not atencion:
                continue

            paciente = atencion.paciente

            # =========================================
            # SERVICIOS DE LA ATENCIÓN
            # =========================================

            atencion_servicios = (
                AtencionServicio.query
                .filter_by(
                    atencion_id=atencion.id
                )
                .order_by(
                    AtencionServicio.orden.asc(),
                    AtencionServicio.id.asc()
                )
                .all()
            )

            servicios = []

            for atencion_servicio in atencion_servicios:
                servicio = db.session.get(
                    Servicio,
                    atencion_servicio.servicio_id
                )

                if not servicio:
                    continue

                servicios.append({
                    'atencion_servicio_id': (
                        atencion_servicio.id
                    ),

                    'servicio_id': (
                        servicio.id
                    ),

                    'codigo': (
                        servicio.codigo
                    ),

                    'nombre': (
                        servicio.nombre
                    ),

                    'estado': (
                        atencion_servicio.estado
                    ),

                    'pagado': (
                        atencion_servicio.pagado
                    ),

                    'area_destino': (
                        {
                            'id': servicio.area.id,
                            'codigo': servicio.area.codigo,
                            'nombre': servicio.area.nombre
                        }
                        if servicio.area
                        else None
                    )
                })

            # =========================================
            # TURNO
            # =========================================

            resultado.append({
                'id': turno.id,

                'numero_turno': (
                    turno.numero_turno
                ),

                'estado': (
                    turno.estado
                ),

                'tipo_prioridad': (
                    turno.tipo_prioridad
                ),

                'fecha_entrada_cola': (
                    turno.fecha_entrada_cola.isoformat()
                    if turno.fecha_entrada_cola
                    else None
                ),

                'atencion': {
                    'id': atencion.id,
                    'folio': atencion.folio,
                    'sede_id': atencion.sede_id,
                    'tipo_llegada': (
                        atencion.tipo_llegada
                    ),
                    'nombre_paciente': (
                        atencion.nombre_paciente
                    )
                },

                'paciente': (
                    {
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
                    }
                    if paciente
                    else None
                ),

                'servicios': servicios
            })

        # =============================================
        # 6. RESPUESTA
        # =============================================

        return jsonify({
            'success': True,

            'sede': (
                sede.to_dict()
            ),

            'area': {
                'id': area_caja.id,
                'codigo': area_caja.codigo,
                'nombre': area_caja.nombre
            },

            'total': (
                len(resultado)
            ),

            'turnos': (
                resultado
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

        # =================================================
        # VALIDAR SEDE
        # =================================================

        sede_id = data.get(
            'sede_id'
        )

        if not sede_id:
            return jsonify({
                'success': False,
                'error': 'sede_id es requerido'
            }), 400

        try:
            sede_id = int(
                sede_id
            )

        except (
            TypeError,
            ValueError
        ):
            return jsonify({
                'success': False,
                'error': 'sede_id no es válido'
            }), 400

        sede = db.session.get(
            Sede,
            sede_id
        )

        if not sede:
            return jsonify({
                'success': False,
                'error': 'Sede no encontrada'
            }), 404

        if not sede.activo:
            return jsonify({
                'success': False,
                'error': 'La sede está inactiva'
            }), 400

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

            sede_id=sede.id,

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
        # =============================================
        # 1. BUSCAR TURNO ACTUAL
        # =============================================

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

        if turno_actual.estado == 'FINALIZADO':
            return jsonify({
                'success': False,
                'error': 'El turno ya está finalizado'
            }), 400

        # =============================================
        # 2. LEER DATOS
        # =============================================

        data = request.get_json(
            silent=True
        ) or {}

        area_destino_id = data.get('area_id')

        if not area_destino_id:
            return jsonify({
                'success': False,
                'error': 'area_id es requerido'
            }), 400

        try:
            area_destino_id = int(area_destino_id)
        except (TypeError, ValueError):
            return jsonify({
                'success': False,
                'error': 'area_id no es válido'
            }), 400

        # =============================================
        # 3. VALIDAR ÁREA DESTINO
        # =============================================

        area_destino = db.session.get(
            Area,
            area_destino_id
        )

        if not area_destino:
            return jsonify({
                'success': False,
                'error': 'Área destino no encontrada'
            }), 404

        # =============================================
        # 4. OBTENER ATENCIÓN Y SEDE
        # =============================================

        atencion = turno_actual.atencion

        if not atencion:
            return jsonify({
                'success': False,
                'error': (
                    'La atención asociada al turno '
                    'no fue encontrada'
                )
            }), 404

        if not atencion.sede_id:
            return jsonify({
                'success': False,
                'error': 'La atención no tiene una sede asignada'
            }), 409

        # =============================================
        # 5. VALIDAR ÁREA DESTINO EN LA SEDE
        # =============================================

        if not area_disponible_en_sede(
            atencion.sede_id,
            area_destino.id
        ):
            sede = db.session.get(
                Sede,
                atencion.sede_id
            )

            nombre_sede = (
                sede.nombre
                if sede
                else f'ID {atencion.sede_id}'
            )

            return jsonify({
                'success': False,
                'error': (
                    f'El área {area_destino.nombre} '
                    f'no está disponible en la sede '
                    f'{nombre_sede}'
                )
            }), 409

                # =============================================
        # 6. VALIDAR SERVICIO OPCIONAL
        # =============================================

        servicio_id = data.get(
            'servicio_id'
        )

        servicio = None
        configuracion_servicio = None

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

            # El servicio debe pertenecer al área
            # a la que estamos intentando enviar
            # al paciente.
            if servicio.area_id != area_destino.id:
                return jsonify({
                    'success': False,
                    'error': (
                        f'El servicio {servicio.nombre} '
                        f'no pertenece al área '
                        f'{area_destino.nombre}'
                    )
                }), 400

            # Validar disponibilidad completa:
            # Servicio global
            # + Área global
            # + Área en sede
            # + Servicio en sede
            configuracion_servicio = (
                obtener_servicio_en_sede(
                    atencion.sede_id,
                    servicio.id
                )
            )

            if not configuracion_servicio:
                sede = db.session.get(
                    Sede,
                    atencion.sede_id
                )

                nombre_sede = (
                    sede.nombre
                    if sede
                    else f'ID {atencion.sede_id}'
                )

                return jsonify({
                    'success': False,
                    'error': (
                        f'El servicio {servicio.nombre} '
                        f'no está disponible en la sede '
                        f'{nombre_sede}'
                    )
                }), 409

            # Un servicio EXTERNO sí está disponible,
            # pero NO debe generar una cola interna.
            if (
                configuracion_servicio.modalidad
                == 'EXTERNO'
            ):
                sede = db.session.get(
                    Sede,
                    atencion.sede_id
                )

                nombre_sede = (
                    sede.nombre
                    if sede
                    else f'ID {atencion.sede_id}'
                )

                return jsonify({
                    'success': False,
                    'error': (
                        f'El servicio {servicio.nombre} '
                        f'es EXTERNO en la sede '
                        f'{nombre_sede} y no puede '
                        f'generar un turno interno en '
                        f'{area_destino.nombre}'
                    ),
                    'modalidad': 'EXTERNO',
                    'servicio_id': servicio.id
                }), 409
        # =============================================
        # 7. VALIDAR DOCTOR OPCIONAL
        # =============================================

        doctor_id = data.get('doctor_id')

        if doctor_id:
            try:
                doctor_id = int(doctor_id)
            except (TypeError, ValueError):
                return jsonify({
                    'success': False,
                    'error': 'doctor_id no es válido'
                }), 400

            doctor = db.session.get(
                Doctor,
                doctor_id
            )

            if not doctor:
                return jsonify({
                    'success': False,
                    'error': 'Doctor no encontrado'
                }), 404

        # =============================================
        # 8. FINALIZAR TURNO ACTUAL
        # =============================================

        ahora = datetime.utcnow()
        estado_anterior = turno_actual.estado

        turno_actual.estado = 'FINALIZADO'
        turno_actual.fecha_fin = ahora

        # =============================================
        # 9. CREAR NUEVO TURNO
        # =============================================

        nuevo_turno = TurnoArea(
            atencion_id=turno_actual.atencion_id,
            area_id=area_destino.id,
            servicio_id=servicio_id,
            doctor_id=doctor_id,
            numero_turno=generar_temporal(),
            tipo_prioridad=data.get(
                'tipo_prioridad',
                turno_actual.tipo_prioridad or 'NORMAL'
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

        # =============================================
        # 10. HISTORIAL
        # =============================================

        usuario = data.get('usuario', 'sistema')

        historial_salida = HistorialTurno(
            turno_area_id=turno_actual.id,
            atencion_id=turno_actual.atencion_id,
            accion='SALIDA_AREA',
            estado_anterior=estado_anterior,
            estado_nuevo='FINALIZADO',
            motivo=data.get('motivo'),
            usuario=usuario
        )

        historial_entrada = HistorialTurno(
            turno_area_id=nuevo_turno.id,
            atencion_id=nuevo_turno.atencion_id,
            accion='ENTRADA_AREA',
            estado_nuevo='ESPERA',
            motivo=f'Derivado a {area_destino.nombre}',
            usuario=usuario
        )

        db.session.add(historial_salida)
        db.session.add(historial_entrada)

        # =============================================
        # 11. GUARDAR
        # =============================================

        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                f'Paciente enviado a {area_destino.nombre}'
            ),
            'turno': serializar_turno_area(nuevo_turno)
        })

    except Exception as e:
        db.session.rollback()

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
