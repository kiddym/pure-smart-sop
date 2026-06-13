"""create tb_procedure_reference

Revision ID: 0004_procedure_reference
Revises: 0003_node_check
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME as MYSQL_DATETIME

revision = "0004_procedure_reference"
down_revision = "0003_node_check"
branch_labels = None
depends_on = None

# Portable datetime: MySQL gets DATETIME(6), SQLite falls back to generic DATETIME.
DATETIME6 = sa.DateTime().with_variant(MYSQL_DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    bind = op.get_bind()
    # 全新库上 0001_sop_baseline (Base.metadata.create_all) 已因模型已注册而建出本表，跳过。
    # 既有库（0001 在本模型存在前已跑）则此处建表。
    if sa.inspect(bind).has_table("tb_procedure_reference"):
        return
    op.create_table(
        "tb_procedure_reference",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("tb_company.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_procedure_id", sa.String(36), sa.ForeignKey("tb_procedure.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_procedure_group_id", sa.String(36), nullable=False),
        sa.Column("relation_type", sa.String(20), nullable=False),
        sa.Column("note", sa.String(500), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    )
    op.create_index("ix_tb_procedure_reference_company_id", "tb_procedure_reference", ["company_id"])
    op.create_index("ix_tb_procedure_reference_is_active", "tb_procedure_reference", ["is_active"])
    op.create_index("ix_tb_procedure_reference_created_at", "tb_procedure_reference", ["created_at"])
    op.create_index("ix_tb_procedure_reference_target_procedure_group_id", "tb_procedure_reference", ["target_procedure_group_id"])
    op.create_index("ix_tb_procedure_reference_source_sort", "tb_procedure_reference", ["source_procedure_id", "sort_order"])


def downgrade() -> None:
    op.drop_index("ix_tb_procedure_reference_source_sort", table_name="tb_procedure_reference")
    op.drop_index("ix_tb_procedure_reference_target_procedure_group_id", table_name="tb_procedure_reference")
    op.drop_index("ix_tb_procedure_reference_created_at", table_name="tb_procedure_reference")
    op.drop_index("ix_tb_procedure_reference_is_active", table_name="tb_procedure_reference")
    op.drop_index("ix_tb_procedure_reference_company_id", table_name="tb_procedure_reference")
    op.drop_table("tb_procedure_reference")
