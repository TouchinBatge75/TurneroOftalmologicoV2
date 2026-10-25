
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.models import Consultorio, Sede, Area, SedeArea
from app import db
from sqlalchemy.exc import IntegrityError


bp_admin_consultorios = Blueprint(
    'admin_consultorios',
    __name__,
    url_prefix='/api/admin/consultorios'
)


@bp_admin_consultorios.route('', methods=['GET'])
@login_required
def listar_consultorios():

    # Solo Administración puede consultar
    # este catálogo por ahora.
    if current_user.rol != 'ADMIN':
        return jsonify({
            'success': False,
            'error': 'Acceso no autorizado'
        }), 403

    sede_id = request.args.get('sede_id', type=int)

    consulta = Consultorio.query

    if sede_id is not None:
        consulta = consulta.filter_by(sede_id=sede_id)

    consultorios = consulta.order_by(
        Consultorio.sede_id,
        Consultorio.codigo
    ).all()

    return jsonify({
        'success': True,
        'total': len(consultorios),
        'consultorios': [
            consultorio.to_dict()
            for consultorio in consultorios
        ]
    }), 200


@bp_admin_consultorios.route('/configuracion', methods=['GET'])
@login_required
def configuracion_consultorios():

    if current_user.rol != 'ADMIN':
        return jsonify({
            'success': False,
            'error': 'Acceso no autorizado'
        }), 403

    sedes = Sede.query.filter_by(
        activo=True
    ).order_by(Sede.nombre).all()

    areas_habilitadas = (
        SedeArea.query
        .join(Area, SedeArea.area_id == Area.id)
        .join(Sede, SedeArea.sede_id == Sede.id)
        .filter(
            SedeArea.activo.is_(True),
            Area.activo.is_(True),
            Sede.activo.is_(True),
            Area.codigo == 'CONSULTA'
        )
        .all()
    )

    return jsonify({
        'success': True,
        'sedes': [
            {
                'id': sede.id,
                'nombre': sede.nombre,
                'codigo': sede.codigo
            }
            for sede in sedes
        ],
        'areas_habilitadas': [
            {
                'sede_id': registro.sede_id,
                'area_id': registro.area_id,
                'area': 'Consulta Médica'
            }
            for registro in areas_habilitadas
        ]
    }), 200



# =====================================================
# REGISTRAR CONSULTORIO
# =====================================================

@bp_admin_consultorios.route('', methods=['POST'])
@login_required
def crear_consultorio():

    # Solo los administradores pueden registrar consultorios.
    if current_user.rol != 'ADMIN':
        return jsonify({
            'success': False,
            'error': 'Acceso no autorizado'
        }), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'success': False,
            'error': 'Se requiere un objeto JSON'
        }), 400

    sede_id = data.get('sede_id')
    area_id = data.get('area_id')
    codigo = str(data.get('codigo') or '').strip().upper()
    nombre = str(data.get('nombre') or '').strip()

    # =============================================
    # VALIDAR DATOS
    # =============================================

    try:
        sede_id = int(sede_id)
        area_id = int(area_id)
    except (TypeError, ValueError):
        return jsonify({
            'success': False,
            'error': 'Sede o área inválida'
        }), 400

    if not codigo or not nombre:
        return jsonify({
            'success': False,
            'error': 'Código y nombre son obligatorios'
        }), 400

    if len(codigo) > 30 or len(nombre) > 120:
        return jsonify({
            'success': False,
            'error': 'Código o nombre demasiado largo'
        }), 400

    # =============================================
    # VALIDAR SEDE Y ÁREA
    # =============================================

    sede = db.session.get(Sede, sede_id)
    area = db.session.get(Area, area_id)

    if not sede or not sede.activo:
        return jsonify({
            'success': False,
            'error': 'Sede inexistente o inactiva'
        }), 400

    if not area or not area.activo:
        return jsonify({
            'success': False,
            'error': 'Área inexistente o inactiva'
        }), 400

    if area.codigo != 'CONSULTA':
        return jsonify({
            'success': False,
            'error': (
                'Por ahora solo se permiten consultorios '
                'en el área de Consulta Médica'
            )
        }), 400

    habilitada = SedeArea.query.filter_by(
        sede_id=sede_id,
        area_id=area_id,
        activo=True
    ).first()

    if not habilitada:
        return jsonify({
            'success': False,
            'error': 'El área no está habilitada en esta sede'
        }), 400

    # =============================================
    # EVITAR DUPLICADOS
    # =============================================

    existente = Consultorio.query.filter_by(
        sede_id=sede_id,
        codigo=codigo
    ).first()

    if existente:
        return jsonify({
            'success': False,
            'error': (
                'Ya existe un consultorio con ese código '
                'en esta sede'
            )
        }), 409

    # =============================================
    # CREAR CONSULTORIO
    # =============================================

    consultorio = Consultorio(
        sede_id=sede_id,
        area_id=area_id,
        codigo=codigo,
        nombre=nombre,
        activo=True
    )

    try:
        db.session.add(consultorio)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Ya existe un consultorio con ese código'
        }), 409

    except Exception:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'No fue posible registrar el consultorio'
        }), 500

    return jsonify({
        'success': True,
        'message': 'Consultorio registrado correctamente',
        'consultorio': consultorio.to_dict()
    }), 201

