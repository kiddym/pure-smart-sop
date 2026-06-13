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
