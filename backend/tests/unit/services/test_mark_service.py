"""mark_service 单测（决策 §五 Q2/Q3/Q9 / editor-behavior §3）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.procedure import Procedure
from app.schemas.node import ChapterCreate
from app.services import chapter_service, mark_service, step_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.12", user_agent="pytest", request_id="r-mk")


def _proc(factory: Factory) -> Procedure:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return factory.procedure(leaf.id)


def _chapter(
    db: Session,
    pid: str,
    title: str = "章",
    parent_id: str | None = None,
    ct: str = "chapter",
    rich: str = "",
):
    return chapter_service.create_chapter(
        db,
        ChapterCreate(
            procedure_id=pid, title=title, parent_id=parent_id, content_type=ct, rich_content=rich
        ),  # type: ignore[arg-type]
        META,
    )


def test_set_mark_status(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id)
    mark_service.set_mark_status(db, ch.id, "step", META)
    db.refresh(ch)
    assert ch.mark_status == "step"


def test_apply_marks_chapter_to_step(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id, title="动作")
    mark_service.set_mark_status(db, ch.id, "step", META)
    result = mark_service.apply_marks(db, proc.id, META)
    assert result.deleted == [ch.id]
    assert len(result.created) == 1
    db.refresh(ch)
    assert ch.is_active is False


def test_apply_marks_content_to_steps(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = _chapter(db, proc.id, title="父")
    content = _chapter(db, proc.id, ct="content", rich="<p>一</p><p>二</p>", parent_id=parent.id)
    mark_service.set_mark_status(db, content.id, "step", META)
    result = mark_service.apply_marks(db, proc.id, META)
    assert len(result.created) == 2
    assert result.deleted == [content.id]


def test_apply_marks_both_siblings_to_step_ok(db: Session, factory: Factory) -> None:
    """关键：同 parent 的两个内容块同批转 step 不应误判互斥（Q9 最终态校验）。"""
    proc = _proc(factory)
    parent = _chapter(db, proc.id, title="父")
    x1 = _chapter(db, proc.id, ct="content", rich="<p>a</p>", parent_id=parent.id)
    x2 = _chapter(db, proc.id, ct="content", rich="<p>b</p>", parent_id=parent.id)
    mark_service.set_mark_status(db, x1.id, "step", META)
    mark_service.set_mark_status(db, x2.id, "step", META)
    result = mark_service.apply_marks(db, proc.id, META)
    assert len(result.created) == 2
    steps = step_service.list_steps(db, procedure_id=proc.id, chapter_id=parent.id)
    assert [s.code for s in steps] == ["1.1", "1.2"]


def test_apply_marks_partial_sibling_conflict(db: Session, factory: Factory) -> None:
    """只标记两兄弟之一 → 应用后 parent 同时含 step 与 content → 拒绝。"""
    proc = _proc(factory)
    parent = _chapter(db, proc.id, title="父")
    x1 = _chapter(db, proc.id, ct="content", rich="<p>a</p>", parent_id=parent.id)
    _chapter(db, proc.id, ct="content", rich="<p>b</p>", parent_id=parent.id)
    mark_service.set_mark_status(db, x1.id, "step", META)
    with pytest.raises(HTTPException) as exc:
        mark_service.apply_marks(db, proc.id, META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_apply_marks_chapter_content_is_noop(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id, title="章")
    mark_service.set_mark_status(db, ch.id, "content", META)
    result = mark_service.apply_marks(db, proc.id, META)
    assert result.created == []
    assert result.deleted == []
    db.refresh(ch)
    assert ch.is_active is True
    assert ch.mark_status == "unmarked"  # 应用后清空


def test_apply_marks_chapter_step_with_children_rejected(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = _chapter(db, proc.id, title="父")
    _chapter(db, proc.id, title="子", parent_id=parent.id)
    mark_service.set_mark_status(db, parent.id, "step", META)
    with pytest.raises(HTTPException) as exc:
        mark_service.apply_marks(db, proc.id, META)
    assert exc.value.detail["code"] == "CHAPTER_HAS_CHILDREN"


def test_apply_marks_preserves_review_marks(db: Session, factory: Factory) -> None:
    # 评审 M1：apply-marks 不得清除 Word 智能解析留下的 'review' 标记
    proc = _proc(factory)
    review = factory.chapter(proc.id, title="待核实", sort_order=0, mark_status="review")
    parent = _chapter(db, proc.id, title="父")
    content = _chapter(db, proc.id, ct="content", rich="<p>x</p>", parent_id=parent.id)
    mark_service.set_mark_status(db, content.id, "step", META)
    mark_service.apply_marks(db, proc.id, META)
    db.refresh(review)
    assert review.is_active is True
    assert review.mark_status == "review"


def test_apply_marks_clears_mark_status(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    a = _chapter(db, proc.id, title="A")
    mark_service.set_mark_status(db, a.id, "content", META)
    mark_service.apply_marks(db, proc.id, META)
    db.refresh(a)
    assert a.mark_status == "unmarked"
