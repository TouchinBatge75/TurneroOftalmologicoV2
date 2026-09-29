"""vincula servicios con solicitudes de area

Revision ID: c61371c23147
Revises: d0268acd3966
Create Date: 2026-09-28 22:24:49.131640

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c61371c23147'
down_revision = 'd0268acd3966'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        'atencion_servicios',
        schema=None
    ) as batch_op:

        batch_op.add_column(
            sa.Column(
                'solicitud_area_id',
                sa.Integer(),
                nullable=True
            )
        )

        batch_op.create_index(
            batch_op.f(
                'ix_atencion_servicios_solicitud_area_id'
            ),
            ['solicitud_area_id'],
            unique=False
        )

        batch_op.create_foreign_key(
            'fk_atencion_servicios_solicitud_area',
            'solicitudes_area',
            ['solicitud_area_id'],
            ['id']
        )


def downgrade():
    with op.batch_alter_table(
        'atencion_servicios',
        schema=None
    ) as batch_op:

        batch_op.drop_constraint(
            'fk_atencion_servicios_solicitud_area',
            type_='foreignkey'
        )

        batch_op.drop_index(
            batch_op.f(
                'ix_atencion_servicios_solicitud_area_id'
            )
        )

        batch_op.drop_column(
            'solicitud_area_id'
        )