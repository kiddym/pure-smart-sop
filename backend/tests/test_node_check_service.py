"""核查点 schema + service。"""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.node_check import CheckCreateIn

pytestmark = pytest.mark.usefixtures("_tenant_ctx")


def test_schema_accepts_ocr():
    m = CheckCreateIn(
        check_type="ocr",
        prompt="读数",
        params={"target_desc": "压力", "match_mode": "range", "expected": {"min": 0, "max": 0.5}},
    )
    assert m.check_type == "ocr"
    assert m.modality == "visual"  # 默认


def test_schema_rejects_unknown_type():
    with pytest.raises(ValidationError):
        CheckCreateIn(check_type="telepathy", params={})


def test_schema_rejects_bad_severity():
    with pytest.raises(ValidationError):
        CheckCreateIn(check_type="safety", severity="nuclear", params={"items": ["gloves"]})


from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.services import node_check_service
from fastapi import HTTPException


def _step(db, status: str = "DRAFT") -> ProcedureNode:
    proc = Procedure(
        procedure_group_id=str(uuid.uuid4()), folder_id=str(uuid.uuid4()),
        code="QC-00001", name="P", level_of_use="reference", version=1,
        status=status, is_current=True,
    )
    db.add(proc); db.flush()
    node = ProcedureNode(procedure_id=proc.id, body="读压力表", kind="step", sort_order=1000)
    db.add(node); db.flush()
    return node


def test_create_and_list(db):
    node = _step(db)
    c = node_check_service.create_check(db, node.id, {
        "check_type": "safety", "params": {"items": ["gloves"]}, "prompt": "戴手套",
    })
    db.commit()
    rows = node_check_service.list_checks(db, node.id)
    assert [r.id for r in rows] == [c.id]
    assert rows[0].procedure_id == node.procedure_id


def test_create_rejects_non_step_node(db):
    node = _step(db)
    node.kind = "node"; db.flush()
    with pytest.raises(HTTPException) as ei:
        node_check_service.create_check(db, node.id, {"check_type": "safety", "params": {"items": ["gloves"]}})
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "NODE_NOT_STEP"


def test_create_rejects_ocr_without_target(db):
    node = _step(db)
    with pytest.raises(HTTPException) as ei:
        node_check_service.create_check(db, node.id, {"check_type": "ocr", "params": {}})
    assert ei.value.status_code == 422
    assert ei.value.detail["code"] == "CHECK_INVALID"


def test_create_rejects_on_published(db):
    node = _step(db, status="PUBLISHED")
    with pytest.raises(HTTPException) as ei:
        node_check_service.create_check(db, node.id, {"check_type": "safety", "params": {"items": ["gloves"]}})
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "PROCEDURE_READONLY"


def test_delete_soft(db):
    node = _step(db)
    c = node_check_service.create_check(db, node.id, {"check_type": "safety", "params": {"items": ["gloves"]}})
    db.commit()
    node_check_service.delete_check(db, c.id); db.commit()
    assert node_check_service.list_checks(db, node.id) == []


def test_create_ocr_happy_path(db):
    node = _step(db)
    c = node_check_service.create_check(db, node.id, {
        "check_type": "ocr",
        "params": {"target_desc": "压力表读数", "match_mode": "range", "expected": {"min": 0, "max": 0.5}},
        "prompt": "对准压力表",
    })
    db.commit()
    rows = node_check_service.list_checks(db, node.id)
    assert [r.id for r in rows] == [c.id]
    assert rows[0].check_type == "ocr"
    assert rows[0].params["match_mode"] == "range"


def test_create_rejects_safety_empty_items(db):
    node = _step(db)
    with pytest.raises(HTTPException) as ei:
        node_check_service.create_check(db, node.id, {"check_type": "safety", "params": {"items": []}})
    assert ei.value.status_code == 422
    assert ei.value.detail["code"] == "CHECK_INVALID"


def test_patch_can_clear_confidence_threshold(db):
    node = _step(db)
    c = node_check_service.create_check(db, node.id, {
        "check_type": "safety", "params": {"items": ["gloves"]}, "confidence_threshold": 0.8,
    })
    db.commit()
    # patch a NOT-NULL field + clear the nullable confidence_threshold
    node_check_service.patch_check(db, c.id, {"prompt": "请戴丁腈手套", "confidence_threshold": None})
    db.commit()
    rows = node_check_service.list_checks(db, node.id)
    assert rows[0].prompt == "请戴丁腈手套"
    assert rows[0].confidence_threshold is None
