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
