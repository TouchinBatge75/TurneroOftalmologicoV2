
"""Vincular servicios de atención con recorridos.

Revision ID: 793b3c8e354e
Revises: 74ece7816f54
Create Date: 2026-11-03 00:32:31.145724
"""

from alembic import op
import sqlalchemy as sa


revision = "793b3c8e354e"
down_revision = "74ece7816f54"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "atencion_servicios",
        schema=None
    ) as batch_op:

        batch_op.add_column(
            sa.Column(
                "recorrido_id",
                sa.Integer(),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                "paso_actual_id",
                sa.Integer(),
                nullable=True
            )
        )

        batch_op.create_index(
            "ix_atencion_servicios_recorrido_id",
            ["recorrido_id"],
            unique=False
        )

        batch_op.create_foreign_key(
            "fk_atencion_servicios_recorrido_id",
            "recorridos_servicio",
            ["recorrido_id"],
            ["id"]
        )

        batch_op.create_foreign_key(
            "fk_atencion_servicios_paso_actual_id",
            "recorrido_pasos",
            ["paso_actual_id"],
            ["id"]
        )


def downgrade():
    with op.batch_alter_table(
        "atencion_servicios",
        schema=None
    ) as batch_op:

        batch_op.drop_constraint(
            "fk_atencion_servicios_paso_actual_id",
            type_="foreignkey"
        )

        batch_op.drop_constraint(
            "fk_atencion_servicios_recorrido_id",
            type_="foreignkey"
        )

        batch_op.drop_index(
            "ix_atencion_servicios_recorrido_id"
        )

        batch_op.drop_column("paso_actual_id")
        batch_op.drop_column("recorrido_id")
