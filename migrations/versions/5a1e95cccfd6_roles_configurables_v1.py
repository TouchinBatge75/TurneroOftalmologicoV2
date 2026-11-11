"""roles_configurables_v1

Revision ID: 5a1e95cccfd6
Revises: 4bf1ed9c5b89
Create Date: 2026-11-10 22:42:49.487805

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5a1e95cccfd6'
down_revision = '4bf1ed9c5b89'
branch_labels = None
depends_on = None


def upgrade():
    # Los operadores y las asignaciones de permisos usan códigos de texto.
    # Se conserva ese esquema y se añade un catálogo referenciado por FK.
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('codigo', sa.String(length=50), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('fecha_creacion', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('codigo', name='uq_roles_codigo'),
    )

    # Primero se cargan los códigos que YA tienen operadores y permisos,
    # para que agregar claves foráneas no rompa datos existentes.
    conexion = op.get_bind()
    inconsistentes = conexion.execute(sa.text('''
        SELECT codigo FROM (
            SELECT rol AS codigo FROM operadores
            UNION SELECT rol FROM rol_permisos
        ) q
        WHERE codigo IS NULL OR btrim(codigo) = ''
        LIMIT 1
    ''')).first()
    if inconsistentes:
        raise RuntimeError('Existen roles vacíos en operadores/rol_permisos; corrija antes de migrar')

    conexion.execute(sa.text('''
        INSERT INTO roles (codigo, nombre, descripcion, activo)
        SELECT codigo,
               CASE codigo
                 WHEN 'ADMIN' THEN 'Administrador general'
                 WHEN 'RECEPCION' THEN 'Recepción / Caja'
                 WHEN 'TRABAJO_SOCIAL' THEN 'Trabajo Social'
                 WHEN 'MEDICO' THEN 'Médico'
                 WHEN 'AREA' THEN 'Personal de áreas'
                 ELSE replace(initcap(replace(codigo, '_', ' ')), '  ', ' ')
               END,
               'Migrado desde roles existentes o catálogo inicial', TRUE
        FROM (
            SELECT rol AS codigo FROM operadores
            UNION SELECT rol FROM rol_permisos
            UNION SELECT unnest(ARRAY['ADMIN','RECEPCION','TRABAJO_SOCIAL','MEDICO','AREA']) AS codigo
        ) existentes
        WHERE TRUE
        ON CONFLICT (codigo) DO NOTHING
    '''))

    op.create_foreign_key(
        'fk_operadores_rol_roles', 'operadores', 'roles',
        ['rol'], ['codigo'], ondelete='RESTRICT'
    )
    op.create_foreign_key(
        'fk_rol_permisos_rol_roles', 'rol_permisos', 'roles',
        ['rol'], ['codigo'], ondelete='RESTRICT'
    )


def downgrade():
    op.drop_constraint('fk_rol_permisos_rol_roles', 'rol_permisos', type_='foreignkey')
    op.drop_constraint('fk_operadores_rol_roles', 'operadores', type_='foreignkey')
    op.drop_table('roles')
