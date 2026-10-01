"""Agrega area previa a areas por sede

Revision ID: e47d83200e0f
Revises: c61371c23147
Create Date: 2026-10-01 00:10:51.387780

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e47d83200e0f'
down_revision = 'c61371c23147'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        'sede_areas',
        schema=None
    ) as batch_op:

        batch_op.add_column(
            sa.Column(
                'area_previa_id',
                sa.Integer(),
                nullable=True
            )
        )

        batch_op.create_index(
            batch_op.f(
                'ix_sede_areas_area_previa_id'
            ),
            ['area_previa_id'],
            unique=False
        )

        batch_op.create_foreign_key(
            'fk_sede_areas_area_previa',
            'areas',
            ['area_previa_id'],
            ['id']
        )


def downgrade():
    with op.batch_alter_table(
        'sede_areas',
        schema=None
    ) as batch_op:

        batch_op.drop_constraint(
            'fk_sede_areas_area_previa',
            type_='foreignkey'
        )

        batch_op.drop_index(
            batch_op.f(
                'ix_sede_areas_area_previa_id'
            )
        )

        batch_op.drop_column(
            'area_previa_id'
        )