"""move source import to versions

Revision ID: 31866895e238
Revises: d9fd562c1d87
Create Date: 2026-09-24 19:53:01.231154+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '31866895e238'
down_revision: Union[str, Sequence[str], None] = 'd9fd562c1d87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('form_template_versions', sa.Column('source_import_id', sa.UUID(), nullable=True))
    op.create_index(
        op.f('ix_form_template_versions_source_import_id'),
        'form_template_versions',
        ['source_import_id'],
        unique=False,
    )
    op.create_foreign_key(
        op.f('fk_form_template_versions_source_import_id_form_imports'),
        'form_template_versions',
        'form_imports',
        ['source_import_id'],
        ['id'],
        ondelete='SET NULL',
    )
    # El documento que ya tenía la plantilla solo se sabe que es de su última versión
    op.execute(
        """
        UPDATE form_template_versions AS v
        SET source_import_id = t.source_import_id
        FROM form_templates AS t
        WHERE v.template_id = t.id
          AND v.version = t.latest_version
          AND t.source_import_id IS NOT NULL
        """
    )
    op.drop_index(op.f('ix_form_templates_source_import_id'), table_name='form_templates')
    op.drop_constraint(op.f('fk_form_templates_source_import_id_form_imports'), 'form_templates', type_='foreignkey')
    op.drop_column('form_templates', 'source_import_id')


def downgrade() -> None:
    op.add_column('form_templates', sa.Column('source_import_id', sa.UUID(), autoincrement=False, nullable=True))
    op.create_foreign_key(
        op.f('fk_form_templates_source_import_id_form_imports'),
        'form_templates',
        'form_imports',
        ['source_import_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_form_templates_source_import_id'), 'form_templates', ['source_import_id'], unique=False)
    op.execute(
        """
        UPDATE form_templates AS t
        SET source_import_id = v.source_import_id
        FROM form_template_versions AS v
        WHERE v.template_id = t.id
          AND v.version = t.latest_version
        """
    )
    op.drop_constraint(
        op.f('fk_form_template_versions_source_import_id_form_imports'), 'form_template_versions', type_='foreignkey'
    )
    op.drop_index(op.f('ix_form_template_versions_source_import_id'), table_name='form_template_versions')
    op.drop_column('form_template_versions', 'source_import_id')
