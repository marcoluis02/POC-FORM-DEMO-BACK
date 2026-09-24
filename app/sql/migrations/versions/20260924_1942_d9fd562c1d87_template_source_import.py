"""template source import

Revision ID: d9fd562c1d87
Revises: 64f4732643d7
Create Date: 2026-09-24 19:42:39.873847+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9fd562c1d87'
down_revision: Union[str, Sequence[str], None] = '64f4732643d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('form_templates', sa.Column('source_import_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_form_templates_source_import_id'), 'form_templates', ['source_import_id'], unique=False)
    op.create_foreign_key(
        op.f('fk_form_templates_source_import_id_form_imports'),
        'form_templates',
        'form_imports',
        ['source_import_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(op.f('fk_form_templates_source_import_id_form_imports'), 'form_templates', type_='foreignkey')
    op.drop_index(op.f('ix_form_templates_source_import_id'), table_name='form_templates')
    op.drop_column('form_templates', 'source_import_id')
