"""0002 迁移的纯转换函数单测：警示 body → 内联警示块包裹。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa

# 动态加载迁移模块（文件名以数字开头，无法常规 import）
_MIG = Path(__file__).resolve().parents[4] / "alembic" / "versions" / "0002_drop_formtype_alert_types.py"
_spec = importlib.util.spec_from_file_location("mig0002", _MIG)
mig0002 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig0002)  # type: ignore[union-attr]


def test_wrap_note_body() -> None:
    assert mig0002.wrap_alert_body("<p>小心台阶</p>", "NOTE") == (
        '<div class="note-block"><p>小心台阶</p></div>'
    )


def test_wrap_caution_body() -> None:
    assert mig0002.wrap_alert_body("<p>设备风险</p>", "CAUTION") == (
        '<div class="caution-block"><p>设备风险</p></div>'
    )


def test_wrap_warning_body() -> None:
    assert mig0002.wrap_alert_body("<p>人身风险</p>", "WARNING") == (
        '<div class="warning-block"><p>人身风险</p></div>'
    )


def test_wrap_empty_body() -> None:
    assert mig0002.wrap_alert_body("", "WARNING") == '<div class="warning-block"></div>'
    assert mig0002.wrap_alert_body(None, "NOTE") == '<div class="note-block"></div>'


def test_wrap_rejects_unknown_type() -> None:
    with pytest.raises(KeyError):
        mig0002.wrap_alert_body("<p>x</p>", "NUMBER")


def test_upgrade_converts_alert_step(tmp_path) -> None:
    """在临时 SQLite 上建最小表，插一条 WARNING 步骤，跑 upgrade 逻辑断言转换。"""
    eng = sa.create_engine(f"sqlite:///{tmp_path}/m.db")
    meta = sa.MetaData()
    node = sa.Table(
        "tb_procedure_node",
        meta,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("kind", sa.String),
        sa.Column("body", sa.Text),
        sa.Column("input_schema", sa.JSON),
        sa.Column("attachment_marks", sa.JSON),
    )
    meta.create_all(eng)
    with eng.begin() as conn:
        conn.execute(
            node.insert(),
            [
                {"id": "a", "kind": "step", "body": "<p>高压</p>",
                 "input_schema": {"type": "WARNING"}, "attachment_marks": [{"filename": "x"}]},
                {"id": "b", "kind": "step", "body": "<p>读数</p>",
                 "input_schema": {"type": "NUMBER"}, "attachment_marks": []},
            ],
        )
    # 复用迁移的纯逻辑跑一遍 update（不经 alembic context）
    with eng.begin() as conn:
        rows = conn.execute(sa.select(node.c.id, node.c.body, node.c.input_schema)
                            .where(node.c.kind == "step")).fetchall()
        for r in rows:
            schema = mig0002._schema_dict(r.input_schema)
            ft = str(schema.get("type", "")).upper()
            if ft not in mig0002._ALERT_TYPE_TO_BLOCK:
                continue
            conn.execute(node.update().where(node.c.id == r.id).values(
                kind="node", body=mig0002.wrap_alert_body(r.body, ft),
                input_schema={}, attachment_marks=[]))
    with eng.connect() as conn:
        a = conn.execute(sa.select(node).where(node.c.id == "a")).one()
        b = conn.execute(sa.select(node).where(node.c.id == "b")).one()
    assert a.kind == "node"
    assert a.body == '<div class="warning-block"><p>高压</p></div>'
    assert a.input_schema == {}
    assert a.attachment_marks == []
    # 非警示步骤不动
    assert b.kind == "step" and b.input_schema == {"type": "NUMBER"}
