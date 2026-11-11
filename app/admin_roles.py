"""Administración de roles — Turnero V2.

El catálogo utiliza los códigos de rol existentes en operadores y rol_permisos.
Todas las mutaciones requieren un ADMIN autenticado con permisos_gestionar.
"""
import re
from flask import Blueprint, jsonify, render_template, request, current_app
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Operador, Permiso, Rol, RolPermiso
from app.permisos import verificar_permiso

bp_admin_roles = Blueprint('admin_roles', __name__)
CODIGO_RE = re.compile(r'^[A-Z][A-Z0-9_]{1,29}$')
CRITICOS_ADMIN = frozenset({'admin_acceder', 'permisos_gestionar'})


def error(mensaje, estado=400):
    return jsonify(success=False, error=mensaje), estado


@bp_admin_roles.before_request
def controlar_acceso():
    if not current_user.is_authenticated:
        return error('Debe iniciar sesión', 401)
    if not current_user.is_active or not current_user.activo:
        return error('Operador inactivo', 403)
    # La gestión de roles se reserva explícitamente al rol ADMIN.
    if current_user.rol != 'ADMIN' or not verificar_permiso('permisos_gestionar'):
        return error('No tiene autorización para administrar roles', 403)


def datos_json():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return None
    return datos


def serializar_rol(rol):
    ids = [p.permiso_id for p in RolPermiso.query.filter_by(rol=rol.codigo).order_by(RolPermiso.permiso_id).all()]
    return {
        'id': rol.id,
        'codigo': rol.codigo,
        'nombre': rol.nombre,
        'descripcion': rol.descripcion or '',
        'activo': bool(rol.activo),
        'fecha_creacion': rol.fecha_creacion.isoformat() if rol.fecha_creacion else None,
        'permisos_ids': ids,
        'total_operadores': Operador.query.filter_by(rol=rol.codigo).count(),
        'operadores_activos': Operador.query.filter_by(rol=rol.codigo, activo=True).count(),
    }


def ids_permisos_validos(datos):
    ids = datos.get('permisos_ids')
    if not isinstance(ids, list) or any(type(i) is not int or i < 1 for i in ids):
        return None
    if len(ids) != len(set(ids)):
        return None
    encontrados = Permiso.query.filter(Permiso.id.in_(ids), Permiso.activo.is_(True)).all() if ids else []
    if len(encontrados) != len(ids):
        return None
    return ids


def validar_admin_criticos(codigo, ids):
    if codigo != 'ADMIN':
        return True
    encontrados = {p.codigo for p in Permiso.query.filter(Permiso.id.in_(ids)).all()}
    return CRITICOS_ADMIN.issubset(encontrados)


@bp_admin_roles.get('/admin/roles')
def pagina_roles():
    return render_template('admin_roles.html')


@bp_admin_roles.get('/api/admin/roles')
def listar_roles():
    roles = Rol.query.order_by(Rol.nombre).all()
    return jsonify(success=True, roles=[serializar_rol(r) for r in roles])


@bp_admin_roles.get('/api/admin/roles/permisos')
def listar_permisos():
    permisos = Permiso.query.filter_by(activo=True).order_by(Permiso.codigo).all()
    return jsonify(success=True, permisos=[{
        'id': p.id,
        'codigo': p.codigo,
        'nombre': p.nombre,
        'descripcion': p.descripcion or '',
    } for p in permisos])


@bp_admin_roles.get('/api/admin/roles/operadores')
def listar_operadores():
    operadores = Operador.query.order_by(Operador.nombre).all()
    return jsonify(success=True, operadores=[{
        'id': o.id, 'usuario': o.usuario, 'nombre': o.nombre,
        'rol': o.rol, 'activo': bool(o.activo),
    } for o in operadores])


@bp_admin_roles.post('/api/admin/roles')
def crear_rol():
    datos = datos_json()
    if datos is None:
        return error('Se requiere un objeto JSON')
    codigo = str(datos.get('codigo') or '').strip().upper()
    nombre = str(datos.get('nombre') or '').strip()
    descripcion = str(datos.get('descripcion') or '').strip()
    if not CODIGO_RE.fullmatch(codigo):
        return error('Código inválido: use 2 a 30 caracteres, letras mayúsculas, números y _')
    if not (2 <= len(nombre) <= 100) or len(descripcion) > 2000:
        return error('Nombre de 2 a 100 caracteres y descripción de máximo 2000')
    if Rol.query.filter_by(codigo=codigo).first():
        return error('El código del rol ya existe', 409)
    try:
        rol = Rol(codigo=codigo, nombre=nombre, descripcion=descripcion, activo=True)
        db.session.add(rol)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error('El código del rol ya existe', 409)
    current_app.logger.warning('Rol creado %s por operador %s', codigo, current_user.id)
    return jsonify(success=True, rol=serializar_rol(rol)), 201


@bp_admin_roles.patch('/api/admin/roles/<int:rol_id>')
def editar_rol(rol_id):
    rol = db.session.get(Rol, rol_id)
    if rol is None:
        return error('Rol inexistente', 404)
    datos = datos_json()
    if datos is None:
        return error('Se requiere un objeto JSON')
    if 'codigo' in datos and datos['codigo'] != rol.codigo:
        return error('El código del rol es inmutable; cree otro rol y reasigne operadores')
    if 'nombre' in datos:
        nombre = str(datos['nombre'] or '').strip()
        if not 2 <= len(nombre) <= 100:
            return error('El nombre debe tener 2 a 100 caracteres')
        rol.nombre = nombre
    if 'descripcion' in datos:
        descripcion = str(datos['descripcion'] or '').strip()
        if len(descripcion) > 2000:
            return error('La descripción excede 2000 caracteres')
        rol.descripcion = descripcion
    if 'activo' in datos:
        if type(datos['activo']) is not bool:
            return error('activo debe ser true o false')
        if not datos['activo'] and rol.codigo == 'ADMIN':
            return error('El rol ADMIN no puede desactivarse', 409)
        if not datos['activo'] and Operador.query.filter_by(rol=rol.codigo, activo=True).count():
            return error('Reasigne o desactive los operadores activos antes de desactivar este rol', 409)
        rol.activo = datos['activo']
    db.session.commit()
    current_app.logger.warning('Rol actualizado %s por operador %s', rol.codigo, current_user.id)
    return jsonify(success=True, rol=serializar_rol(rol))


@bp_admin_roles.put('/api/admin/roles/<int:rol_id>/permisos')
def reemplazar_permisos(rol_id):
    rol = db.session.get(Rol, rol_id)
    if rol is None:
        return error('Rol inexistente', 404)
    if not rol.activo:
        return error('No se pueden editar permisos de un rol inactivo', 409)
    datos = datos_json()
    if datos is None:
        return error('Se requiere un objeto JSON')
    ids = ids_permisos_validos(datos)
    if ids is None:
        return error('permisos_ids debe ser una lista de IDs únicos de permisos activos')
    if not validar_admin_criticos(rol.codigo, ids):
        return error('ADMIN debe conservar admin_acceder y permisos_gestionar', 409)
    # Transacción: se reemplaza el conjunto completo, no se acumulan duplicados.
    try:
        RolPermiso.query.filter_by(rol=rol.codigo).delete(synchronize_session=False)
        db.session.add_all(RolPermiso(rol=rol.codigo, permiso_id=pid) for pid in ids)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error('Conflicto al guardar permisos', 409)
    current_app.logger.warning('Permisos de rol %s actualizados por operador %s', rol.codigo, current_user.id)
    return jsonify(success=True, rol=serializar_rol(rol))


@bp_admin_roles.put('/api/admin/roles/operadores/<int:operador_id>/rol')
def cambiar_rol_operador(operador_id):
    datos = datos_json()
    if datos is None:
        return error('Se requiere un objeto JSON')
    codigo = str(datos.get('rol') or '').strip().upper()
    rol = Rol.query.filter_by(codigo=codigo, activo=True).first()
    if rol is None:
        return error('El rol de destino no existe o está inactivo', 400)
    operador = db.session.get(Operador, operador_id)
    if operador is None:
        return error('Operador inexistente', 404)
    if operador.id == current_user.id and operador.rol != codigo:
        return error('No puede cambiar su propio rol', 409)
    if operador.rol == 'ADMIN' and codigo != 'ADMIN' and operador.activo:
        admins = Operador.query.filter_by(rol='ADMIN', activo=True).count()
        if admins <= 1:
            return error('No se puede dejar el sistema sin un ADMIN activo', 409)
    operador.rol = codigo
    db.session.commit()
    current_app.logger.warning('Rol del operador %s cambiado a %s por %s', operador.id, codigo, current_user.id)
    return jsonify(success=True, operador={
        'id': operador.id, 'usuario': operador.usuario,
        'nombre': operador.nombre, 'rol': operador.rol,
    })
