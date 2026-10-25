
from flask import Blueprint, jsonify, request
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user
)

from app.models import Operador


bp = Blueprint(
    'auth',
    __name__,
    url_prefix='/auth'
)


@bp.route('/login', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return jsonify({
            'success': False,
            'error': 'Ya existe una sesión activa'
        }), 409

    data = request.get_json(silent=True) or {}

    if not isinstance(data, dict):
        return jsonify({
            'success': False,
            'error': 'El cuerpo debe ser un objeto JSON'
        }), 400

    usuario = str(
        data.get('usuario') or ''
    ).strip()

    password = data.get('password')

    if not usuario or not isinstance(password, str):
        return jsonify({
            'success': False,
            'error': 'Usuario y contraseña requeridos'
        }), 400

    operador = Operador.query.filter_by(
        usuario=usuario
    ).first()

    if (
        operador is None
        or not operador.activo
        or not operador.verificar_password(password)
    ):
        return jsonify({
            'success': False,
            'error': 'Credenciales incorrectas'
        }), 401

    login_user(operador)

    return jsonify({
        'success': True,
        'message': 'Sesión iniciada',
        'operador': {
            'id': operador.id,
            'nombre': operador.nombre,
            'usuario': operador.usuario,
            'rol': operador.rol,
            'sede_id': operador.sede_id
        }
    })


@bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify({
        'success': True,
        'operador': {
            'id': current_user.id,
            'nombre': current_user.nombre,
            'usuario': current_user.usuario,
            'rol': current_user.rol,
            'sede_id': current_user.sede_id
        }
    })


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()

    return jsonify({
        'success': True,
        'message': 'Sesión cerrada'
    })
