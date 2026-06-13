"""SOP 参考关系 service：增删查改 + 校验 + 目标当前版本解析。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import conflict, not_found, unprocessable
from app.models.base import utcnow
from app.models.procedure import Procedure
from app.models.procedure_reference import ProcedureReference
from app.services import procedure_service

_SORT_GAP = 1000


def _current_in_group(db: Session, group_id: str) -> Procedure | None:
    """解析逻辑 SOP（group）的当前版本（租户作用域自动生效）。"""
    stmt = select(Procedure).where(
        Procedure.procedure_group_id == group_id,
        Procedure.is_current.is_(True),
        Procedure.is_active.is_(True),
    )
    return db.execute(stmt).scalars().first()


def _get_reference(db: Session, reference_id: str) -> ProcedureReference:
    ref = db.get(ProcedureReference, reference_id)
    if ref is None or not ref.is_active:
        raise not_found("REFERENCE_NOT_FOUND", "参考关系不存在")
    return ref


def list_references(db: Session, source_procedure_id: str) -> list[ProcedureReference]:
    stmt = (
        select(ProcedureReference)
        .where(
            ProcedureReference.source_procedure_id == source_procedure_id,
            ProcedureReference.is_active.is_(True),
        )
        .order_by(ProcedureReference.sort_order, ProcedureReference.id)
    )
    return list(db.execute(stmt).scalars())


def serialize(db: Session, ref: ProcedureReference) -> dict[str, Any]:
    """补上目标当前版本快照（code/name/version/具体版本 id）；无当前版本则为 None。"""
    target = _current_in_group(db, ref.target_procedure_group_id)
    return {
        "id": ref.id,
        "source_procedure_id": ref.source_procedure_id,
        "target_procedure_group_id": ref.target_procedure_group_id,
        "relation_type": ref.relation_type,
        "note": ref.note,
        "sort_order": ref.sort_order,
        "target_procedure_id": target.id if target else None,
        "target_code": target.code if target else None,
        "target_name": target.name if target else None,
        "target_version": target.version if target else None,
    }


def create_reference(db: Session, source_procedure_id: str, data: dict[str, Any]) -> ProcedureReference:
    source = procedure_service.get_or_404(db, source_procedure_id)
    procedure_service.assert_node_host_editable(db, source_procedure_id)

    target_group = data["target_procedure_group_id"]
    if target_group == source.procedure_group_id:
        raise unprocessable("REFERENCE_SELF", "不能引用自身 SOP")
    if _current_in_group(db, target_group) is None:
        raise unprocessable("REFERENCE_TARGET_NOT_FOUND", "目标 SOP 不存在或无当前版本")

    relation_type = data["relation_type"]
    dup = db.execute(
        select(ProcedureReference).where(
            ProcedureReference.source_procedure_id == source_procedure_id,
            ProcedureReference.target_procedure_group_id == target_group,
            ProcedureReference.relation_type == relation_type,
            ProcedureReference.is_active.is_(True),
        )
    ).scalars().first()
    if dup is not None:
        raise conflict("REFERENCE_DUPLICATE", "同一目标的同类型引用已存在")

    if data.get("sort_order") is not None:
        sort_order = data["sort_order"]
    else:
        existing = list_references(db, source_procedure_id)
        sort_order = (existing[-1].sort_order + _SORT_GAP) if existing else _SORT_GAP

    ref = ProcedureReference(
        source_procedure_id=source_procedure_id,
        target_procedure_group_id=target_group,
        relation_type=relation_type,
        note=data.get("note", ""),
        sort_order=sort_order,
    )
    db.add(ref)
    db.flush()
    return ref


def patch_reference(db: Session, reference_id: str, changes: dict[str, Any]) -> ProcedureReference:
    ref = _get_reference(db, reference_id)
    procedure_service.assert_node_host_editable(db, ref.source_procedure_id)
    for key in ("relation_type", "note", "sort_order"):
        if key in changes and changes[key] is not None:
            setattr(ref, key, changes[key])
    db.flush()
    return ref


def delete_reference(db: Session, reference_id: str) -> None:
    ref = _get_reference(db, reference_id)
    procedure_service.assert_node_host_editable(db, ref.source_procedure_id)
    ref.is_active = False
    ref.deleted_at = utcnow()
    db.flush()
