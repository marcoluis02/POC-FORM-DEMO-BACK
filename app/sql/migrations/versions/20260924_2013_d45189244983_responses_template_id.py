"""responses template id

Revision ID: d45189244983
Revises: 31866895e238
Create Date: 2026-09-24 20:13:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd45189244983'
down_revision: Union[str, Sequence[str], None] = '31866895e238'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('form_responses', sa.Column('template_id', sa.UUID(), nullable=True))
    # Si ya hay respuestas, su plantilla sale de la versión que usaron
    op.execute(
        """
        UPDATE form_responses AS r
        SET template_id = v.template_id
        FROM form_template_versions AS v
        WHERE r.template_version_id = v.id
        """
    )
    op.alter_column('form_responses', 'template_id', nullable=False)
    op.create_index(
        'ix_form_responses_template_id_created_at_id',
        'form_responses',
        ['template_id', 'created_at', 'id'],
        unique=False,
    )
    op.create_foreign_key(
        op.f('fk_form_responses_template_id_form_templates'),
        'form_responses',
        'form_templates',
        ['template_id'],
        ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint(op.f('fk_form_responses_template_id_form_templates'), 'form_responses', type_='foreignkey')
    op.drop_index('ix_form_responses_template_id_created_at_id', table_name='form_responses')
    op.drop_column('form_responses', 'template_id')
