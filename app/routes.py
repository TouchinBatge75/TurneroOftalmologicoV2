# app/routes.py
from flask import Blueprint, jsonify, request
from app import db
from app.models import Doctor, Turno
from datetime import datetime

bp = Blueprint('api', __name__, url_prefix='/api')

# ========== RUTAS DE PRUEBA ==========
@bp.route('/')
def api_index():
    return jsonify({
        'app': 'Turnero Oftalmológico API',
        'version': '2.0',
        'status': 'running',
        'endpoints': {
            'doctores': '/api/doctores',
            'turnos': '/api/turnos',
            'test': '/api/test'
        }
    })

@bp.route('/test')
def test():
    return jsonify({
        'success': True,
        'message': '✅ API funcionando correctamente',
        'timestamp': datetime.now().isoformat()
    })

# ========== DOCTORES ==========
@bp.route('/doctores', methods=['GET'])
def get_doctores():
    """Obtener todos los doctores"""
    try:
        doctores = Doctor.query.all()
        return jsonify({
            'success': True,
            'doctores': [d.to_dict() for d in doctores],
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
    """Obtener un doctor específico"""
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor no encontrado'}), 404
    
    return jsonify({
        'success': True,
        'doctor': doctor.to_dict()
    })

# ========== TURNOS ==========
@bp.route('/turnos', methods=['GET'])
def get_turnos():
    """Obtener todos los turnos"""
    try:
        turnos = Turno.query.all()
        return jsonify({
            'success': True,
            'turnos': [t.to_dict() for t in turnos],
            'total': len(turnos)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/turnos/nuevo', methods=['POST'])
def crear_turno():
    """Crear nuevo turno (simplificado)"""
    try:
        data = request.json or {}
        
        # Validación básica
        if not data.get('paciente_nombre') or not data.get('paciente_edad'):
            return jsonify({
                'success': False,
                'error': 'Faltan datos requeridos: paciente_nombre, paciente_edad'
            }), 400
        
        # Generar número de turno simple
        ultimo = Turno.query.order_by(Turno.id.desc()).first()
        consecutivo = 1 if not ultimo else int(ultimo.id) + 1
        numero = f"T{consecutivo:03d}"
        
        # Crear turno
        turno = Turno(
            numero=numero,
            paciente_nombre=data['paciente_nombre'],
            paciente_edad=int(data['paciente_edad']),
            tipo=data.get('tipo', 'SIN_CITA'),
            estado=data.get('estado', 'PENDIENTE'),
            estacion_actual=data.get('estacion_actual', 1)
        )
        
        db.session.add(turno)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Turno {numero} creado',
            'turno': turno.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
@bp.route('/doctores/<int:doctor_id>/actualizar-estado', methods=['PUT'])
def actualizar_estado_doctor(doctor_id):
    """Actualizar estado, consultorio y enfermero de un doctor"""
    try:
        data = request.json
        doctor = Doctor.query.get_or_404(doctor_id)
        
        # Actualizar campos
        if 'activo' in data:
            doctor.activo = bool(data['activo'])
        if 'disponible' in data:
            doctor.disponible = bool(data['disponible'])
        if 'estado' in data:
            doctor.estado = data['estado']
        if 'consultorio' in data:
            doctor.consultorio = data['consultorio']
        if 'enfermero_asignado' in data:
            doctor.enfermero_asignado = data['enfermero_asignado']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Doctor {doctor.nombre} actualizado',
            'doctor': doctor.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
@bp.route('/doctores/estado')
def get_estado_doctores():
    """Obtener estado de todos los doctores para el dashboard"""
    try:
        doctores = Doctor.query.all()
        
        # Estadísticas
        total = len(doctores)
        activos = sum(1 for d in doctores if d.activo)
        disponibles = sum(1 for d in doctores if d.disponible)
        
        return jsonify({
            'success': True,
            'doctores': [d.to_dict() for d in doctores],
            'estadisticas': {
                'total': total,
                'activos': activos,
                'disponibles': disponibles,
                'ocupados': total - disponibles,
                'inactivos': total - activos
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
    # Devuelve doctores con consultorio y enfermero
    pass

@bp.route('/turnos/<int:turno_id>/mover', methods=['POST'])
def mover_turno(turno_id):
    # Mueve entre estaciones
    pass