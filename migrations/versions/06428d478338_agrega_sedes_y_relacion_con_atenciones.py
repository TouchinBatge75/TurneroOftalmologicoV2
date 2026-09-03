"""Agrega sedes y relacion con atenciones

Revision ID: 06428d478338
Revises: e76520dcc61a
"""

from alembic import op
import sqlalchemy as sa


revision = '06428d478338'
down_revision = 'e76520dcc61a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'sedes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=30), nullable=False),
        sa.Column('nombre', sa.String(length=120), nullable=False),
        sa.Column('direccion', sa.String(length=255), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False),
        sa.Column('fecha_creacion', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(
        'ix_sedes_codigo',
        'sedes',
        ['codigo'],
        unique=True
    )

    op.add_column(
        'atenciones',
        sa.Column(
            'sede_id',
            sa.Integer(),
            nullable=True
        )
    )

    op.create_index(
        'ix_atenciones_sede_id',
        'atenciones',
        ['sede_id'],
        unique=False
    )

    op.create_foreign_key(
        None,
        'atenciones',
        'sedes',
        ['sede_id'],
        ['id']
    )


def downgrade():
    op.drop_constraint(
        None,
        'atenciones',
        type_='foreignkey'
    )

    op.drop_index(
        'ix_atenciones_sede_id',
        table_name='atenciones'
    )

    op.drop_column(
        'atenciones',
        'sede_id'
    )

    op.drop_index(
        'ix_sedes_codigo',
        table_name='sedes'
    )

    op.drop_table('sedes')
