"""Parche seguro e idempotente para agregar roles configurables.

Uso (desde raíz Turnero): python tools/preparar_roles.py
Hace respaldo de app/models.py y app/__init__.py. Genera una nueva
revisión Alembic usando el HEAD real del proyecto, SIN aplicar a BD.
"""
import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / 'app' / 'models.py'
INIT = ROOT / 'app' / '__init__.py'
TEMPLATE = ROOT / 'plantillas' / 'migracion_roles.py.txt'
VERSIONS = ROOT / 'migrations' / 'versions'


def reemplazar_unico(texto, viejo, nuevo, descripcion):
    if nuevo in texto:
        return texto
    apariciones = texto.count(viejo)
    if apariciones != 1:
        raise RuntimeError(f'{descripcion}: se esperó una coincidencia, encontradas {apariciones}. No se modificó el proyecto.')
    return texto.replace(viejo, nuevo, 1)


def ajustar_modelos(texto):
    if "class Rol(db.Model):" not in texto:
        bloque = '''class Rol(db.Model):
    """Catálogo central de roles configurables; codigo es la referencia estable."""
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False)
    __table_args__ = (db.UniqueConstraint('codigo', name='uq_roles_codigo'),)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    activo = db.Column(db.Boolean, nullable=False, default=True, server_default='true')
    fecha_creacion = db.Column(db.DateTime, nullable=False, server_default=db.func.now())


'''
        texto = reemplazar_unico(texto, 'class Operador(UserMixin, db.Model):', bloque + 'class Operador(UserMixin, db.Model):', 'Insertar Rol')

    ini = texto.index('class Operador(UserMixin, db.Model):')
    fin = texto.index('class Consultorio(db.Model):', ini)
    parte = texto[ini:fin]
    viejo = """    rol = db.Column(
        db.String(30),
        nullable=False,
        default='AREA'
    )"""
    nuevo = """    rol = db.Column(
        db.String(30),
        db.ForeignKey('roles.codigo', ondelete='RESTRICT'),
        nullable=False,
        default='AREA'
    )

    rol_detalle = db.relationship('Rol', foreign_keys=[rol])"""
    parte = reemplazar_unico(parte, viejo, nuevo, 'FK de Operador.rol')
    parte = reemplazar_unico(
        parte, 'return bool(self.activo)',
        'return bool(self.activo and self.rol_detalle and self.rol_detalle.activo)',
        'Bloqueo de operadores con rol inactivo',
    )
    texto = texto[:ini] + parte + texto[fin:]

    ini = texto.index('class RolPermiso(db.Model):')
    fin = texto.index('class OperadorPermiso(db.Model):', ini)
    parte = texto[ini:fin]
    parte = reemplazar_unico(
        parte,
        'rol = db.Column(db.String(50), nullable=False)',
        "rol = db.Column(db.String(50), db.ForeignKey('roles.codigo', ondelete='RESTRICT'), nullable=False)",
        'FK de RolPermiso.rol',
    )
    return texto[:ini] + parte + texto[fin:]


def ajustar_init(texto):
    # Quitar únicamente un import a nivel global, en caso de que se haya pegado ahí.
    prefijo, resto = texto.split('def create_app():', 1)
    prefijo = re.sub(r'^from app import panel_medicos\s*\n', '', prefijo, flags=re.M)
    texto = prefijo + 'def create_app():' + resto
    if 'app.register_blueprint(admin_roles.bp_admin_roles)' not in texto:
        bloque = '''    # ADMINISTRACION DE ROLES CONFIGURABLES
    from app import admin_roles
    app.register_blueprint(admin_roles.bp_admin_roles)

'''
        # Insertar ANTES de las interfaces/rutas. No requiere modificar blueprints anteriores.
        indice = texto.find('    from app.permisos import verificar_permiso, verificar_area')
        if indice < 0:
            raise RuntimeError('No se encontró el import de permisos en __init__.py')
        texto = texto[:indice] + bloque + texto[indice:]
    if "url_for('admin_roles.pagina_roles')" not in texto:
        inicio = texto.index("@app.route('/mi-panel')")
        fin = texto.index("@app.route('/recepcion')", inicio)
        fragmento = texto[inicio:fin]
        marcador = '        if operador_puede_recepcion():'
        if fragmento.count(marcador) != 1:
            raise RuntimeError('No se identificó el destino Recepción en mi_panel()')
        fragmento = fragmento.replace(marcador, '''        # Hasta que exista un Dashboard Admin completo, dirigir al catálogo de roles.
        if current_user.rol == 'ADMIN' and verificar_permiso('permisos_gestionar'):
            return redirect(url_for('admin_roles.pagina_roles'))

''' + marcador, 1)
        texto = texto[:inicio] + fragmento + texto[fin:]
    return texto


def crear_revision():
    if not VERSIONS.is_dir():
        raise RuntimeError('No existe migrations/versions; revisa el entorno Alembic')
    existentes = set(VERSIONS.glob('*.py'))
    comando = [sys.executable, '-m', 'flask', 'db', 'revision', '-m', 'roles_configurables_v1']
    print('Generando revision con HEAD real:', ' '.join(comando))
    subprocess.run(comando, cwd=ROOT, check=True)
    nuevos = list(set(VERSIONS.glob('*.py')) - existentes)
    if len(nuevos) != 1:
        raise RuntimeError('No pude identificar una única migración creada. Revísala manualmente.')
    archivo = nuevos[0]
    encabezado = archivo.read_text(encoding='utf-8')
    patron = re.search(r'^def upgrade\(', encabezado, re.M)
    if not patron:
        raise RuntimeError(f'No encontré upgrade() en {archivo}')
    cuerpo = TEMPLATE.read_text(encoding='utf-8')
    migracion = encabezado[:patron.start()] + cuerpo
    ast.parse(migracion)
    archivo.write_text(migracion, encoding='utf-8')
    print('Migración creada (aún NO aplicada):', archivo.relative_to(ROOT))


def main():
    if not (MODELS.is_file() and INIT.is_file() and TEMPLATE.is_file()):
        raise RuntimeError('Faltan archivos del proyecto o de este paquete')
    modelos_original = MODELS.read_text(encoding='utf-8')
    init_original = INIT.read_text(encoding='utf-8')
    modelos_nuevo = ajustar_modelos(modelos_original)
    init_nuevo = ajustar_init(init_original)
    ast.parse(modelos_nuevo, filename=str(MODELS))
    ast.parse(init_nuevo, filename=str(INIT))
    if modelos_nuevo != modelos_original:
        shutil.copy2(MODELS, MODELS.with_name('models.pre_roles.bak'))
        MODELS.write_text(modelos_nuevo, encoding='utf-8')
        print('app/models.py actualizado (respaldo: models.pre_roles.bak)')
    if init_nuevo != init_original:
        shutil.copy2(INIT, INIT.with_name('__init__.pre_roles.bak'))
        INIT.write_text(init_nuevo, encoding='utf-8')
        print('app/__init__.py actualizado (respaldo: __init__.pre_roles.bak)')
    existentes = list(VERSIONS.glob('*roles_configurables_v1.py'))
    if existentes:
        print('Ya existe una revisión de roles. No se creará otra:', existentes[0].name)
    else:
        crear_revision()
    print('Preparado. Revisa la migración y ejecuta: python -m flask db upgrade')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, subprocess.CalledProcessError, SyntaxError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
