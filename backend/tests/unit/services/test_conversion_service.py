"""conversion_service 单测（决策 §五 Q1-Q12 / §19 / 错误码 §二十三）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.procedure import Procedure
from app.schemas.node import ChapterCreate, StepCreate
from app.services import chapter_service, conversion_service, step_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.11", user_agent="pytest", request_id="r-cv")


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


# --------------------------------------------------------------------------- #
# 顶层块拆分
# --------------------------------------------------------------------------- #
def test_split_top_level_blocks() -> None:
    blocks = conversion_service.split_top_level_blocks(
        "<p>第一段</p><ul><li>a</li><li>b</li></ul><table><tr><td>x</td></tr></table>"
    )
    assert len(blocks) == 3
    assert blocks[0] == "<p>第一段</p>"
    assert blocks[1].startswith("<ul>")
    assert blocks[2].startswith("<table>")


def test_split_empty_returns_single_block() -> None:
    assert conversion_service.split_top_level_blocks("") == [""]


def test_split_preserves_void_tags_no_data_loss() -> None:
    # 评审 C1：<img> 等空元素不得吞掉其后顶层块
    blocks = conversion_service.split_top_level_blocks('<p>说明</p><img src="/a.png"><p>结尾</p>')
    assert blocks == ["<p>说明</p>", '<img src="/a.png">', "<p>结尾</p>"]


def test_split_void_tag_inside_block_keeps_single_block() -> None:
    blocks = conversion_service.split_top_level_blocks("<p>a<br>b</p><p>c</p>")
    assert blocks == ["<p>a<br>b</p>", "<p>c</p>"]


def test_split_loose_top_level_entity_preserved() -> None:
    # 评审 H1：顶层游离文本中的实体不丢、不误拆
    blocks = conversion_service.split_top_level_blocks("题注 &amp; 更多")
    assert blocks == ["题注 &amp; 更多"]


# --------------------------------------------------------------------------- #
# chapter → step
# --------------------------------------------------------------------------- #
def test_convert_chapter_to_step(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id, title="单章")
    result = conversion_service.convert_to_step(db, ch.id, META)
    assert result.deleted == [ch.id]
    assert len(result.created) == 1
    db.refresh(ch)
    assert ch.is_active is False
    step = step_service.get_step(db, result.created[0])
    assert step.title == "单章"
    assert step.content == ""
    assert step.code == "1"  # 根级 step


def test_convert_chapter_with_children_rejected(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = _chapter(db, proc.id, title="父")
    _chapter(db, proc.id, title="子", parent_id=parent.id)
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_step(db, parent.id, META)
    assert exc.value.detail["code"] == "CHAPTER_HAS_CHILDREN"


def test_convert_chapter_to_step_sibling_conflict(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    a = _chapter(db, proc.id, title="A")
    _chapter(db, proc.id, title="B")  # 同级仍有章节
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_step(db, a.id, META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_convert_root_to_step_requires_root(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = _chapter(db, proc.id, title="父")
    child = _chapter(db, proc.id, title="子", parent_id=parent.id)
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_root_to_step(db, child.id, META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


# --------------------------------------------------------------------------- #
# content → steps
# --------------------------------------------------------------------------- #
def test_content_to_steps(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = _chapter(db, proc.id, title="父")
    content = _chapter(db, proc.id, ct="content", rich="<p>一</p><p>二</p>", parent_id=parent.id)
    result = conversion_service.content_to_steps(db, content.id, META)
    assert len(result.created) == 2
    assert result.deleted == [content.id]
    steps = step_service.list_steps(db, procedure_id=proc.id, chapter_id=parent.id)
    assert [s.code for s in steps] == ["1.1", "1.2"]


def test_content_to_steps_sibling_conflict(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = _chapter(db, proc.id, title="父")
    c1 = _chapter(db, proc.id, ct="content", rich="<p>x</p>", parent_id=parent.id)
    _chapter(db, proc.id, ct="content", rich="<p>y</p>", parent_id=parent.id)  # 同级另有 content
    with pytest.raises(HTTPException) as exc:
        conversion_service.content_to_steps(db, c1.id, META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_batch_content_to_steps(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    p1 = _chapter(db, proc.id, title="父1")
    p2 = _chapter(db, proc.id, title="父2")
    c1 = _chapter(db, proc.id, ct="content", rich="<p>a</p>", parent_id=p1.id)
    c2 = _chapter(db, proc.id, ct="content", rich="<p>b</p><p>c</p>", parent_id=p2.id)
    result = conversion_service.batch_content_to_steps(db, [c1.id, c2.id], META)
    assert len(result.created) == 3
    assert set(result.deleted) == {c1.id, c2.id}


# --------------------------------------------------------------------------- #
# step → chapter
# --------------------------------------------------------------------------- #
def test_convert_step_to_chapter_with_body(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = _chapter(db, proc.id, title="父")
    step = step_service.create_step(
        db,
        StepCreate(procedure_id=proc.id, chapter_id=parent.id, title="步骤", content="<p>正文</p>"),
        META,
    )
    result = conversion_service.convert_to_chapter(db, step.id, META)
    assert result.deleted == [step.id]
    assert len(result.created) == 2  # 新 chapter + 承载正文的 content 子节点
    new_chapter = chapter_service.get_chapter(db, result.created[0])
    assert new_chapter.content_type == "chapter"
    assert new_chapter.rich_content == ""  # §19：chapter 不承载正文
    content_child = chapter_service.get_chapter(db, result.created[1])
    assert content_child.content_type == "content"
    assert "正文" in content_child.rich_content


def test_convert_step_to_chapter_sibling_conflict(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    parent = _chapter(db, proc.id, title="父")
    s1 = step_service.create_step(db, StepCreate(procedure_id=proc.id, chapter_id=parent.id), META)
    step_service.create_step(
        db, StepCreate(procedure_id=proc.id, chapter_id=parent.id), META
    )  # 同级另有 step
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_chapter(db, s1.id, META)
    assert exc.value.detail["code"] == "SIBLING_TYPE_CONFLICT"


def test_convert_step_to_chapter_depth_exceeded(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    l1 = _chapter(db, proc.id, title="1")
    l2 = _chapter(db, proc.id, title="2", parent_id=l1.id)
    l3 = _chapter(db, proc.id, title="3", parent_id=l2.id)
    step = step_service.create_step(db, StepCreate(procedure_id=proc.id, chapter_id=l3.id), META)
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_chapter(db, step.id, META)
    assert exc.value.detail["code"] == "CHAPTER_DEPTH_EXCEEDED"


# --------------------------------------------------------------------------- #
# chapter → content（废弃）
# --------------------------------------------------------------------------- #
def test_convert_to_content_gone(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id)
    with pytest.raises(HTTPException) as exc:
        conversion_service.convert_to_content(db, ch.id, META)
    assert exc.value.status_code == 410
    assert exc.value.detail["code"] == "CONVERT_TO_CONTENT_DEPRECATED"
