"""ProcedureNodeCheck 模型：核查点挂到 step 节点。"""
from __future__ import annotations

import uuid

import pytest

from app.models.node import ProcedureNode
from app.models.node_check import ProcedureNodeCheck
from app.models.procedure import Procedure

pytestmark = pytest.mark.usefixtures("_tenant_ctx")


def _step_node(db) -> ProcedureNode:
    proc = Procedure(
        procedure_group_id=str(uuid.uuid4()),
        folder_id=str(uuid.uuid4()),
        code="QC-00001",
        name="P",
        level_of_use="reference",
        version=1,
        status="DRAFT",
        is_current=True,
    )
    db.add(proc)
    db.flush()
    node = ProcedureNode(
        procedure_id=proc.id, body="读压力表", kind="step", sort_order=1000
    )
    db.add(node)
    db.flush()
    return node


def test_create_and_query_check(db):
    node = _step_node(db)
    check = ProcedureNodeCheck(
        node_id=node.id,
        procedure_id=node.procedure_id,
        check_type="ocr",
        modality="visual",
        severity="warn",
        trigger="manual",
        prompt="请将压力表对准镜头",
        params={"target_desc": "压力表读数", "match_mode": "range", "expected": {"min": 0, "max": 0.5}, "unit": "MPa"},
        sort_order=1000,
    )
    db.add(check)
    db.commit()

    rows = db.query(ProcedureNodeCheck).filter_by(node_id=node.id, is_active=True).all()
    assert len(rows) == 1
    assert rows[0].check_type == "ocr"
    assert rows[0].params["unit"] == "MPa"
    assert rows[0].company_id  # before_flush 自动注入
