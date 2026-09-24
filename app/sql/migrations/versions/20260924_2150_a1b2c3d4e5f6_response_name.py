"""Nombre personalizado en cada formulario llenado

Revision ID: a1b2c3d4e5f6
Revises: d45189244983
Create Date: 2026-09-24 21:50:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "d45189244983"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("form_responses", sa.Column("name", sa.String(length=200), nullable=True))
    # Los llenados que ya existían quedan con un nombre simple hasta que el usuario los edite
    op.execute(sa.text("UPDATE form_responses SET name = 'Formulario' WHERE name IS NULL"))
    op.alter_column("form_responses", "name", existing_type=sa.String(length=200), nullable=False)


def downgrade() -> None:
    op.drop_column("form_responses", "name")
