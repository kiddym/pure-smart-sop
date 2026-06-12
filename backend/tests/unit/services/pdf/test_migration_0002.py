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
    """在临时 SQLite 上建最小表，插 WARNING/NUMBER/NOTE/CAUTION 步骤，
    调用真实共用 helper _convert_alert_steps，断言转换结果。"""
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
                {"id": "c", "kind": "step", "body": "<p>注意</p>",
                 "input_schema": {"type": "NOTE"}, "attachment_marks": []},
                {"id": "d", "kind": "step", "body": "<p>小心</p>",
                 "input_schema": {"type": "CAUTION"}, "attachment_marks": []},
            ],
        )
    # 调用真实共用 helper（不经 alembic context）
    with eng.begin() as conn:
        mig0002._convert_alert_steps(conn)
    with eng.connect() as conn:
        a = conn.execute(sa.select(node).where(node.c.id == "a")).one()
        b = conn.execute(sa.select(node).where(node.c.id == "b")).one()
        c = conn.execute(sa.select(node).where(node.c.id == "c")).one()
        d = conn.execute(sa.select(node).where(node.c.id == "d")).one()
    assert a.kind == "node"
    assert a.body == '<div class="warning-block"><p>高压</p></div>'
    assert a.input_schema == {}
    assert a.attachment_marks == []
    # 非警示步骤不动
    assert b.kind == "step" and b.input_schema == {"type": "NUMBER"}
    # NOTE 转换
    assert c.kind == "node"
    assert c.body == '<div class="note-block"><p>注意</p></div>'
    # CAUTION 转换
    assert d.kind == "node"
    assert d.body == '<div class="caution-block"><p>小心</p></div>'
