"""create tb_procedure_node_check

Revision ID: 0003_node_check
Revises: 0002_drop_formtype_alert_types
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME as MYSQL_DATETIME

revision = "0003_node_check"
down_revision = "0002_drop_formtype_alert_types"
branch_labels = None
depends_on = None

# Portable datetime: MySQL gets DATETIME(6), SQLite falls back to generic DATETIME.
DATETIME6 = sa.DateTime().with_variant(MYSQL_DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    bind = op.get_bind()
    # On a fresh DB, 0001_sop_baseline (Base.metadata.create_all) already created
    # this table + its indexes because the ORM model is registered. Skip in that case.
    # On an existing DB that ran 0001 before this model existed, the table is absent
    # and we create it here.
    if sa.inspect(bind).has_table("tb_procedure_node_check"):
        return
    op.create_table(
        "tb_procedure_node_check",
        # --- UUIDMixin ---
        sa.Column("id", sa.String(36), primary_key=True),
        # --- TenantMixin ---
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # --- domain columns ---
        sa.Column(
            "node_id",
            sa.String(36),
            sa.ForeignKey("tb_procedure_node.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "procedure_id",
            sa.String(36),
            sa.ForeignKey("tb_procedure.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("check_type", sa.String(20), nullable=False),
        sa.Column("modality", sa.String(20), nullable=False, server_default="visual"),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warn"),
        sa.Column("trigger", sa.String(20), nullable=False, server_default="on_enter"),
        sa.Column("prompt", sa.String(500), nullable=False, server_default=""),
        sa.Column("keep_evidence", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("confidence_threshold", sa.Float(), nullable=True),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        # --- SoftDeleteMixin ---
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        # --- TimestampMixin ---
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    )
    # Single-column indexes from mixin index=True declarations.
    op.create_index("ix_tb_procedure_node_check_company_id", "tb_procedure_node_check", ["company_id"])
    op.create_index("ix_tb_procedure_node_check_procedure_id", "tb_procedure_node_check", ["procedure_id"])
    op.create_index("ix_tb_procedure_node_check_is_active", "tb_procedure_node_check", ["is_active"])
    op.create_index("ix_tb_procedure_node_check_created_at", "tb_procedure_node_check", ["created_at"])
    # Composite index covering node_id lookups — replaces any standalone node_id index.
    op.create_index("ix_tb_procedure_node_check_node_id_sort_order", "tb_procedure_node_check", ["node_id", "sort_order"])


def downgrade() -> None:
    op.drop_index(
        "ix_tb_procedure_node_check_node_id_sort_order",
        table_name="tb_procedure_node_check",
    )
    op.drop_index(
        "ix_tb_procedure_node_check_created_at",
        table_name="tb_procedure_node_check",
    )
    op.drop_index(
        "ix_tb_procedure_node_check_is_active",
        table_name="tb_procedure_node_check",
    )
    op.drop_index(
        "ix_tb_procedure_node_check_procedure_id",
        table_name="tb_procedure_node_check",
    )
    op.drop_index(
        "ix_tb_procedure_node_check_company_id",
        table_name="tb_procedure_node_check",
    )
    op.drop_table("tb_procedure_node_check")
