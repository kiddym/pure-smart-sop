"""核查点 service：增删查改 + 校验 + 编辑守卫。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request, not_found, unprocessable
from app.models.base import utcnow
from app.models.node import ProcedureNode
from app.models.node_check import ProcedureNodeCheck
from app.services import node_service

_SORT_GAP = 1000
_NULLABLE_FIELDS = frozenset({"confidence_threshold"})


def _validate_params(check_type: str, params: dict[str, Any]) -> None:
    if check_type == "ocr":
        if not str(params.get("target_desc", "")).strip():
            raise unprocessable("CHECK_INVALID", "ocr 核查需要非空 target_desc")
        if params.get("match_mode") not in {"exact", "contains", "regex", "range"}:
            raise unprocessable("CHECK_INVALID", "ocr 核查 match_mode 必须是 exact/contains/regex/range")
    elif check_type == "safety":
        items = params.get("items")
        if not isinstance(items, list) or not items:
            raise unprocessable("CHECK_INVALID", "safety 核查需要非空 items 列表")
    else:  # pragma: no cover - schema 已挡，双保险
        raise unprocessable("CHECK_INVALID", f"第一期不支持 check_type={check_type}")


def _get_step_node(db: Session, node_id: str) -> ProcedureNode:
    node = db.get(ProcedureNode, node_id)
    if node is None or not node.is_active:
        raise not_found("NODE_NOT_FOUND", "节点不存在")
    if node.kind != "step":
        raise bad_request("NODE_NOT_STEP", "仅 step 节点可挂核查点")
    return node


def _get_check(db: Session, check_id: str) -> ProcedureNodeCheck:
    c = db.get(ProcedureNodeCheck, check_id)
    if c is None or not c.is_active:
        raise not_found("CHECK_NOT_FOUND", "核查点不存在")
    return c


def list_checks(db: Session, node_id: str) -> list[ProcedureNodeCheck]:
    stmt = (
        select(ProcedureNodeCheck)
        .where(ProcedureNodeCheck.node_id == node_id, ProcedureNodeCheck.is_active.is_(True))
        .order_by(ProcedureNodeCheck.sort_order, ProcedureNodeCheck.id)
    )
    return list(db.execute(stmt).scalars())


def create_check(db: Session, node_id: str, data: dict[str, Any]) -> ProcedureNodeCheck:
    node = _get_step_node(db, node_id)
    node_service._assert_procedure_editable(db, node.procedure_id)
    check_type = data["check_type"]
    params = data.get("params", {})
    _validate_params(check_type, params)

    if data.get("sort_order") is not None:
        sort_order = data["sort_order"]
    else:
        existing = list_checks(db, node_id)
        sort_order = (existing[-1].sort_order + _SORT_GAP) if existing else _SORT_GAP

    check = ProcedureNodeCheck(
        node_id=node.id,
        procedure_id=node.procedure_id,
        check_type=check_type,
        modality=data.get("modality", "visual"),
        severity=data.get("severity", "warn"),
        trigger=data.get("trigger", "on_enter"),
        prompt=data.get("prompt", ""),
        keep_evidence=data.get("keep_evidence", True),
        confidence_threshold=data.get("confidence_threshold"),
        params=params,
        sort_order=sort_order,
    )
    db.add(check)
    db.flush()
    return check


def patch_check(db: Session, check_id: str, changes: dict[str, Any]) -> ProcedureNodeCheck:
    check = _get_check(db, check_id)
    node_service._assert_procedure_editable(db, check.procedure_id)
    if "params" in changes and changes["params"] is not None:
        _validate_params(check.check_type, changes["params"])
    for key in ("modality", "severity", "trigger", "prompt", "keep_evidence", "confidence_threshold", "params", "sort_order"):
        if key not in changes:
            continue
        if changes[key] is None and key not in _NULLABLE_FIELDS:
            continue
        setattr(check, key, changes[key])
    db.flush()
    return check


def delete_check(db: Session, check_id: str) -> None:
    check = _get_check(db, check_id)
    node_service._assert_procedure_editable(db, check.procedure_id)
    check.is_active = False
    check.deleted_at = utcnow()
    db.flush()
