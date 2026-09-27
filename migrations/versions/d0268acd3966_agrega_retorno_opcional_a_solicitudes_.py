"""Agrega retorno opcional a solicitudes de area

Revision ID: d0268acd3966
Revises: 5b99816ccab7
Create Date: 2026-09-26 23:04:26.916289

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd0268acd3966'
down_revision = '5b99816ccab7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        'solicitudes_area',
        schema=None
    ) as batch_op:

        # ---------------------------------------------
        # Retorno
        #
        # Los server_default permiten migrar registros
        # existentes sin violar NOT NULL.
        # ---------------------------------------------

        batch_op.add_column(
            sa.Column(
                'tipo_retorno',
                sa.String(length=30),
                nullable=False,
                server_default='NINGUNO'
            )
        )

        batch_op.add_column(
            sa.Column(
                'estado_retorno',
                sa.String(length=30),
                nullable=False,
                server_default='NO_APLICA'
            )
        )

        batch_op.add_column(
            sa.Column(
                'area_retorno_id',
                sa.Integer(),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                'doctor_retorno_id',
                sa.Integer(),
                nullable=True
            )
        )

        # ---------------------------------------------
        # Índices
        # ---------------------------------------------

        batch_op.create_index(
            batch_op.f(
                'ix_solicitudes_area_area_retorno_id'
            ),
            ['area_retorno_id'],
            unique=False
        )

        batch_op.create_index(
            batch_op.f(
                'ix_solicitudes_area_doctor_retorno_id'
            ),
            ['doctor_retorno_id'],
            unique=False
        )

        # ---------------------------------------------
        # Foreign keys
        # ---------------------------------------------

        batch_op.create_foreign_key(
            'fk_solicitudes_area_area_retorno',
            'areas',
            ['area_retorno_id'],
            ['id']
        )

        batch_op.create_foreign_key(
            'fk_solicitudes_area_doctor_retorno',
            'doctores',
            ['doctor_retorno_id'],
            ['id']
        )

        # ---------------------------------------------
        # Quitamos defaults de BD después de rellenar
        # registros existentes.
        #
        # Los nuevos registros usarán los defaults
        # definidos en el modelo SQLAlchemy.
        # ---------------------------------------------

        batch_op.alter_column(
            'tipo_retorno',
            server_default=None
        )

        batch_op.alter_column(
            'estado_retorno',
            server_default=None
        )


def downgrade():
    with op.batch_alter_table(
        'solicitudes_area',
        schema=None
    ) as batch_op:

        batch_op.drop_constraint(
            'fk_solicitudes_area_doctor_retorno',
            type_='foreignkey'
        )

        batch_op.drop_constraint(
            'fk_solicitudes_area_area_retorno',
            type_='foreignkey'
        )

        batch_op.drop_index(
            batch_op.f(
                'ix_solicitudes_area_doctor_retorno_id'
            )
        )

        batch_op.drop_index(
            batch_op.f(
                'ix_solicitudes_area_area_retorno_id'
            )
        )

        batch_op.drop_column(
            'doctor_retorno_id'
        )

        batch_op.drop_column(
            'area_retorno_id'
        )

        batch_op.drop_column(
            'estado_retorno'
        )

        batch_op.drop_column(
            'tipo_retorno'
        )