"""ProcedureNode.source_style_name (M2) + tb_heading_learning_event (M3，单租户)

Revision ID: heading_learning
Revises: heading_style_rule
Create Date: 2026-05-31

Hand-authored (MySQL prod + SQLite dev/test)。append-only 事件表：BIGINT/SQLite INTEGER 自增。
单租户：投票全局聚合；租户分区（company_id）留待 P2。
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "heading_learning"
down_revision: str | Sequence[str] | None = "heading_style_rule"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # M2：节点来源样式名（nullable，SQLite 加列无需 batch）
    op.add_column(
        "tb_procedure_node",
        sa.Column("source_style_name", sa.String(length=255), nullable=True),
    )
    # M3：学习事件表（append-only；BIGINT/SQLite INTEGER 自增）
    op.create_table(
        "tb_heading_learning_event",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
            autoincrement=True,
        ),
        sa.Column("procedure_id", sa.String(length=36), nullable=False),
        sa.Column("node_id", sa.String(length=36), nullable=False),
        sa.Column("style_name", sa.String(length=255), nullable=False),
        sa.Column("signal_type", sa.String(length=30), nullable=False),
        sa.Column("from_level", sa.Integer(), nullable=True),
        sa.Column("to_level", sa.Integer(), nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tb_heading_learning_event_procedure_id",
        "tb_heading_learning_event",
        ["procedure_id"],
    )
    op.create_index(
        "ix_tb_heading_learning_event_style_name",
        "tb_heading_learning_event",
        ["style_name"],
    )
    op.create_index(
        "ix_tb_heading_learning_event_style_name_procedure_id",
        "tb_heading_learning_event",
        ["style_name", "procedure_id"],
    )


def downgrade() -> None:
    op.drop_table("tb_heading_learning_event")
    op.drop_column("tb_procedure_node", "source_style_name")
