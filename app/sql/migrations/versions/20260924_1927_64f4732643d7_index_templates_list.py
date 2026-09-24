"""index templates list

Revision ID: 64f4732643d7
Revises: e71156204e9c
Create Date: 2026-09-24 19:27:13.492174+00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = '64f4732643d7'
down_revision: Union[str, Sequence[str], None] = 'e71156204e9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_form_templates_created_at_id', 'form_templates', ['created_at', 'id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_form_templates_created_at_id', table_name='form_templates')
