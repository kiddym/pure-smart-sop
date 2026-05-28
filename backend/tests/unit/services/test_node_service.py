"""ProcedureNode 服务与不变量单测。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services._invariants import enforce_node_invariants


def test_node_kind_with_input_schema_rejected() -> None:
    with pytest.raises(HTTPException):
        enforce_node_invariants(
            kind="node", heading_level=None, input_schema={"type": "COMMON"}, attachment_marks=[]
        )


def test_step_kind_with_heading_level_rejected() -> None:
    with pytest.raises(HTTPException):
        enforce_node_invariants(
            kind="step", heading_level=2, input_schema={"type": "COMMON"}, attachment_marks=[]
        )


def test_heading_level_zero_rejected() -> None:
    with pytest.raises(HTTPException):
        enforce_node_invariants(
            kind="node", heading_level=0, input_schema={}, attachment_marks=[]
        )


def test_valid_heading_node_ok() -> None:
    enforce_node_invariants(kind="node", heading_level=2, input_schema={}, attachment_marks=[])


def test_valid_content_node_ok() -> None:
    enforce_node_invariants(kind="node", heading_level=None, input_schema={}, attachment_marks=[])


def test_valid_step_ok() -> None:
    enforce_node_invariants(
        kind="step", heading_level=None, input_schema={"type": "COMMON"}, attachment_marks=[]
    )
