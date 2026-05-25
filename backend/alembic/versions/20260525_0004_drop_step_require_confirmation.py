"""backfill signoff_enabled then drop step.require_confirmation

Revision ID: drop_step_require_confirmation
Revises: add_procedure_signoff
Create Date: 2026-05-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'drop_step_require_confirmation'
down_revision: str | None = 'add_procedure_signoff'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 保留意图到程序级：任一步骤勾过 → 该 procedure.signoff_enabled = 1
    op.get_bind().execute(sa.text(
        "UPDATE tb_procedure SET signoff_enabled = 1 WHERE id IN "
        "(SELECT DISTINCT procedure_id FROM tb_procedure_step WHERE require_confirmation = 1)"
    ))
    with op.batch_alter_table('tb_procedure_step') as batch:
        batch.drop_column('require_confirmation')


def downgrade() -> None:
    with op.batch_alter_table('tb_procedure_step') as batch:
        batch.add_column(sa.Column('require_confirmation', sa.Boolean(), nullable=False, server_default='0'))
