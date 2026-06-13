"""SOP 参考关系：模型 + schema + service。"""
from __future__ import annotations

import uuid

import pytest

from app.models.procedure import Procedure
from app.models.procedure_reference import ProcedureReference

pytestmark = pytest.mark.usefixtures("_tenant_ctx")


def _proc(db, status: str = "DRAFT", group_id: str | None = None, is_current: bool = True) -> Procedure:
    proc = Procedure(
        procedure_group_id=group_id or str(uuid.uuid4()),
        folder_id=str(uuid.uuid4()),
        code="QC-00001",
        name="P",
        level_of_use="reference",
        version=1,
        status=status,
        is_current=is_current,
    )
    db.add(proc)
    db.flush()
    return proc


def test_create_and_query_reference(db):
    src = _proc(db)
    tgt = _proc(db)
    ref = ProcedureReference(
        source_procedure_id=src.id,
        target_procedure_group_id=tgt.procedure_group_id,
        relation_type="exec_ref",
        note="隔离前先确认上游阀位",
        sort_order=1000,
    )
    db.add(ref)
    db.commit()

    rows = db.query(ProcedureReference).filter_by(source_procedure_id=src.id, is_active=True).all()
    assert len(rows) == 1
    assert rows[0].relation_type == "exec_ref"
    assert rows[0].target_procedure_group_id == tgt.procedure_group_id
    assert rows[0].company_id  # before_flush 自动注入


from pydantic import ValidationError

from app.schemas.procedure_reference import ReferenceCreateIn


def test_schema_accepts_valid():
    m = ReferenceCreateIn(target_procedure_group_id=str(uuid.uuid4()), relation_type="authoring_ref")
    assert m.relation_type == "authoring_ref"
    assert m.note == ""  # 默认


def test_schema_rejects_unknown_relation_type():
    with pytest.raises(ValidationError):
        ReferenceCreateIn(target_procedure_group_id=str(uuid.uuid4()), relation_type="sibling")


def test_schema_rejects_missing_target():
    with pytest.raises(ValidationError):
        ReferenceCreateIn(relation_type="related")


from fastapi import HTTPException

from app.services import procedure_reference_service


def test_create_and_serialize(db):
    src = _proc(db)
    tgt = _proc(db)  # 独立 group，is_current=True
    ref = procedure_reference_service.create_reference(db, src.id, {
        "target_procedure_group_id": tgt.procedure_group_id,
        "relation_type": "exec_ref",
        "note": "先隔离上游",
    })
    db.commit()
    rows = procedure_reference_service.list_references(db, src.id)
    assert [r.id for r in rows] == [ref.id]
    out = procedure_reference_service.serialize(db, rows[0])
    assert out["target_code"] == "QC-00001"
    assert out["target_procedure_id"] == tgt.id
    assert out["target_version"] == 1


def test_create_rejects_self_reference(db):
    src = _proc(db)
    with pytest.raises(HTTPException) as ei:
        procedure_reference_service.create_reference(db, src.id, {
            "target_procedure_group_id": src.procedure_group_id, "relation_type": "related",
        })
    assert ei.value.status_code == 422
    assert ei.value.detail["code"] == "REFERENCE_SELF"


def test_create_rejects_unknown_target(db):
    src = _proc(db)
    with pytest.raises(HTTPException) as ei:
        procedure_reference_service.create_reference(db, src.id, {
            "target_procedure_group_id": str(uuid.uuid4()), "relation_type": "related",
        })
    assert ei.value.status_code == 422
    assert ei.value.detail["code"] == "REFERENCE_TARGET_NOT_FOUND"


def test_create_rejects_duplicate(db):
    src = _proc(db)
    tgt = _proc(db)
    payload = {"target_procedure_group_id": tgt.procedure_group_id, "relation_type": "related"}
    procedure_reference_service.create_reference(db, src.id, dict(payload))
    db.commit()
    with pytest.raises(HTTPException) as ei:
        procedure_reference_service.create_reference(db, src.id, dict(payload))
    assert ei.value.status_code == 409
    assert ei.value.detail["code"] == "REFERENCE_DUPLICATE"


def test_create_rejects_on_published_source(db):
    src = _proc(db, status="PUBLISHED")
    tgt = _proc(db)
    with pytest.raises(HTTPException) as ei:
        procedure_reference_service.create_reference(db, src.id, {
            "target_procedure_group_id": tgt.procedure_group_id, "relation_type": "related",
        })
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "PROCEDURE_READONLY"


def test_delete_soft(db):
    src = _proc(db)
    tgt = _proc(db)
    ref = procedure_reference_service.create_reference(db, src.id, {
        "target_procedure_group_id": tgt.procedure_group_id, "relation_type": "related",
    })
    db.commit()
    procedure_reference_service.delete_reference(db, ref.id)
    db.commit()
    assert procedure_reference_service.list_references(db, src.id) == []
