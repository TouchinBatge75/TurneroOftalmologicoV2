"""Crear operador de prueba Trabajo Social, sede Orizaba, con permisos limitados.
Uso: python crear_operador_ts.py desde raiz del proyecto Turnero.
"""
from getpass import getpass
import sys
from app import create_app, db
from app.models import Operador, OperadorArea, Sede, Area, Permiso, OperadorPermiso

USUARIO = 'trabajo_social_prueba'
NOMBRE = 'Trabajo Social Prueba'
SEDE_CODIGO = 'ORIZABA'
AREA_CODIGO = 'TRABAJO_SOCIAL'
PERMISOS = (
    'trabajo_social_ver',
    'trabajo_social_afiliar',
    'turnos_ver',
    'turnos_llamar',
    'turnos_iniciar',
)


def main():
    app = create_app()
    with app.app_context():
        existente = Operador.query.filter_by(usuario=USUARIO).first()
        if existente:
            print(f'El usuario {USUARIO} ya existe (ID {existente.id}). No se ha modificado.')
            return 0

        sede = Sede.query.filter_by(codigo=SEDE_CODIGO, activo=True).first()
        area = Area.query.filter_by(codigo=AREA_CODIGO, activo=True).first()
        if not sede or not area:
            print('ERROR: Falta la sede ORIZABA o el área TRABAJO_SOCIAL activas.')
            return 1

        codigos = {p.codigo: p for p in Permiso.query.filter(Permiso.codigo.in_(PERMISOS), Permiso.activo.is_(True)).all()}
        faltantes = set(PERMISOS) - set(codigos)
        if faltantes:
            print('ERROR: Estos permisos no están dados de alta:', ', '.join(sorted(faltantes)))
            print('No se realizaron cambios. Revisa la tabla permisos antes de crear el operador.')
            return 1

        clave = getpass('Contraseña nueva para trabajo_social_prueba: ')
        confirmacion = getpass('Repite la contraseña: ')
        if clave != confirmacion or len(clave) < 12:
            print('ERROR: las contraseñas no coinciden o tienen menos de 12 caracteres.')
            return 1

        try:
            operador = Operador(
                nombre=NOMBRE,
                usuario=USUARIO,
                rol='TRABAJO_SOCIAL',
                sede_id=sede.id,
                proveedor_identidad='LOCAL',
                activo=True,
            )
            operador.establecer_password(clave)
            db.session.add(operador)
            db.session.flush()
            db.session.add(OperadorArea(
                operador_id=operador.id,
                sede_id=sede.id,
                area_id=area.id,
                activo=True,
            ))
            for codigo in PERMISOS:
                db.session.add(OperadorPermiso(
                    operador_id=operador.id,
                    permiso_id=codigos[codigo].id,
                    permitido=True,
                ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        print('\nOperador creado correctamente')
        print('Usuario:', operador.usuario)
        print('Rol:', operador.rol)
        print('Sede:', sede.nombre)
        print('Área:', area.nombre)
        print('Permisos:', ', '.join(PERMISOS))
        print('Contraseña: configurada y almacenada como hash (no se muestra)')
        print('Abre /login y después /trabajo-social')
        return 0


if __name__ == '__main__':
    sys.exit(main())
