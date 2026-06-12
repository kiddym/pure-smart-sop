"""删除 FormType 警示类型：把 kind='step' 且 type∈{NOTE,CAUTION,WARNING} 的节点
改写为正文节点(kind='node')，body 用内联警示块整体包裹，清空 input_schema/attachment_marks。

不可逆数据迁移：downgrade 为 no-op，回滚请从备份恢复（见实施计划环境说明）。
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "0002_drop_formtype_alert_types"
down_revision = "0001_sop_baseline"
branch_labels = None
depends_on = None

# FormType 警示值 → 内联块 class（与 constants.BLOCK_CLASS_TO_ALERT 反向一致）
_ALERT_TYPE_TO_BLOCK = {
    "NOTE": "note-block",
    "CAUTION": "caution-block",
    "WARNING": "warning-block",
}


def wrap_alert_body(body: str | None, alert_type: str) -> str:
    """把原警示步骤 body 整体包进对应的内联警示块 div。"""
    cls = _ALERT_TYPE_TO_BLOCK[alert_type]
    return f'<div class="{cls}">{body or ""}</div>'


def _schema_dict(raw: object) -> dict:
    if isinstance(raw, str):
        try:
            return json.loads(raw) or {}
        except (ValueError, TypeError):
            return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _convert_alert_steps(bind) -> None:
    """把所有 kind='step' 且 type∈警示 的节点改写为内联警示块正文节点。upgrade() 与测试共用此逻辑。"""
    node = sa.table(
        "tb_procedure_node",
        sa.column("id", sa.String),
        sa.column("kind", sa.String),
        sa.column("body", sa.Text),
        sa.column("input_schema", sa.JSON),
        sa.column("attachment_marks", sa.JSON),
    )
    rows = bind.execute(
        sa.select(node.c.id, node.c.body, node.c.input_schema).where(node.c.kind == "step")
    ).fetchall()
    for r in rows:
        schema = _schema_dict(r.input_schema)
        ftype = str(schema.get("type", "")).upper()
        if ftype not in _ALERT_TYPE_TO_BLOCK:
            continue
        bind.execute(
            sa.update(node)
            .where(node.c.id == r.id)
            .values(
                kind="node",
                body=wrap_alert_body(r.body, ftype),
                input_schema={},
                attachment_marks=[],
            )
        )


def upgrade() -> None:
    _convert_alert_steps(op.get_bind())


def downgrade() -> None:
    # 不可逆：原 step/title/编号/附件标记无法可靠还原；回滚请从备份恢复。
    pass
