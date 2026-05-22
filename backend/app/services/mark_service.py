"""标记模式业务逻辑（决策 §五 Q2/Q3/Q9 / editor-behavior §3）。

mark_status 仅作用于 chapter / content 节点（step 不参与，Q264）。三态：unmarked / step / content。
「应用标记」= 原子事务（Q9），按 Q2/Q3 语义映射批量转换：

| content_type | mark | 应用 |
|---|---|---|
| chapter | step | convert-to-step（须为叶子，否则 CHAPTER_HAS_CHILDREN）|
| chapter | content | 无操作（§19 后 chapter 无正文可承载）|
| content | step | content-to-steps（按顶层 HTML 块拆分）|
| content | content | 无操作 |

互斥校验取「应用后的最终状态」（Q29）：某 parent 下只要有子节点转 step，则该 parent 的所有
chapter/content 子节点必须**全部**转 step——否则 parent 将同时含 step 与 chapter/content，违反 Q25。
失败全部回滚（router 不 commit），mark_status 保持不变；成功后清空相关节点 mark_status。

事务边界：只 flush，不 commit；结构变更 bump 程序 revision。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request, not_found
from app.models.base import utcnow
from app.models.chapter import ProcedureChapter
from app.models.procedure import Procedure
from app.models.step import ProcedureStep
from app.schemas.node import ApplyMarksResult
from app.services import audit_service, numbering_service, optimistic_lock
from app.services.conversion_service import split_top_level_blocks


def _get_proc_editable(db: Session, proc_id: str) -> Procedure:
    proc = db.execute(
        select(Procedure).where(Procedure.id == proc_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        raise not_found("NOT_FOUND", "程序不存在")
    if not (proc.is_current and proc.status == "DRAFT"):
        raise bad_request("PROCEDURE_READONLY", "仅当前版本的草稿可编辑")
    return proc


def _get_chapter(db: Session, chapter_id: str) -> ProcedureChapter:
    ch = db.execute(
        select(ProcedureChapter).where(
            ProcedureChapter.id == chapter_id, ProcedureChapter.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if ch is None:
        raise not_found("NOT_FOUND", "节点不存在")
    return ch


def set_mark_status(
    db: Session, chapter_id: str, mark_status: str, meta: RequestMeta
) -> ProcedureChapter:
    """设置单个 chapter/content 节点的 mark_status（频繁、不记审计 Q122、不 bump revision）。"""
    ch = _get_chapter(db, chapter_id)
    _get_proc_editable(db, ch.procedure_id)
    ch.mark_status = mark_status
    db.flush()
    return ch


def _has_children(db: Session, chapter_id: str) -> bool:
    has_chapter = (
        db.execute(
            select(ProcedureChapter.id).where(
                ProcedureChapter.parent_id == chapter_id, ProcedureChapter.is_active.is_(True)
            )
        ).first()
        is not None
    )
    has_step = (
        db.execute(
            select(ProcedureStep.id).where(
                ProcedureStep.chapter_id == chapter_id, ProcedureStep.is_active.is_(True)
            )
        ).first()
        is not None
    )
    return has_chapter or has_step


def _active_children(db: Session, proc_id: str, parent_id: str | None) -> list[ProcedureChapter]:
    return list(
        db.execute(
            select(ProcedureChapter)
            .where(
                ProcedureChapter.procedure_id == proc_id,
                ProcedureChapter.parent_id.is_(parent_id)
                if parent_id is None
                else ProcedureChapter.parent_id == parent_id,
                ProcedureChapter.is_active.is_(True),
            )
            .order_by(ProcedureChapter.sort_order, ProcedureChapter.id)
        ).scalars()
    )


def apply_marks(db: Session, proc_id: str, meta: RequestMeta) -> ApplyMarksResult:
    proc = _get_proc_editable(db, proc_id)

    # 仅取标记模式产生的 step/content 标记；不碰 'review'（Word 智能解析的持久态）
    marked = list(
        db.execute(
            select(ProcedureChapter).where(
                ProcedureChapter.procedure_id == proc.id,
                ProcedureChapter.is_active.is_(True),
                ProcedureChapter.mark_status.in_(["step", "content"]),
            )
        ).scalars()
    )
    # 仅 mark='step' 触发转换；mark='content' 一律无操作（§19）
    step_targets = [n for n in marked if n.mark_status == "step"]

    # 1. 校验：chapter→step 必须为叶子
    for n in step_targets:
        if n.content_type == "chapter" and _has_children(db, n.id):
            raise bad_request("CHAPTER_HAS_CHILDREN", f"章节「{n.title}」含子节点，不能转为步骤")

    # 2. 校验：最终状态互斥（按 parent 分组，Q29）
    target_ids = {n.id for n in step_targets}
    parents = {n.parent_id for n in step_targets}
    for parent_id in parents:
        children = _active_children(db, proc.id, parent_id)
        remaining = [c for c in children if c.id not in target_ids]
        if remaining:
            raise bad_request(
                "SIBLING_TYPE_CONFLICT", "同级仍有未转换的章节 / 内容块，应用会违反互斥规则"
            )

    # 3. 执行（已全量校验，按 parent 顺序分配 step sort_order）
    created: list[str] = []
    deleted: list[str] = []
    now = utcnow()
    by_parent: dict[str | None, list[ProcedureChapter]] = {}
    for n in step_targets:
        by_parent.setdefault(n.parent_id, []).append(n)

    for parent_id, nodes in by_parent.items():
        nodes.sort(key=lambda c: (c.sort_order, c.id))
        seq = 0
        for n in nodes:
            if n.content_type == "chapter":
                step = ProcedureStep(
                    procedure_id=proc.id,
                    chapter_id=parent_id,
                    title=n.title,
                    content="",
                    input_schema={"type": "COMMON"},
                    sort_order=seq,
                )
                db.add(step)
                db.flush()
                created.append(step.id)
                seq += 1
                _audit(
                    db,
                    proc,
                    target_id=step.id,
                    action="convert-to-step",
                    meta=meta,
                    old_value={"chapter_id": n.id},
                )
            else:
                blocks = split_top_level_blocks(n.rich_content)
                block_ids: list[str] = []
                for block in blocks:
                    step = ProcedureStep(
                        procedure_id=proc.id,
                        chapter_id=parent_id,
                        title="",
                        content=block,
                        input_schema={"type": "COMMON"},
                        sort_order=seq,
                    )
                    db.add(step)
                    db.flush()
                    created.append(step.id)
                    block_ids.append(step.id)
                    seq += 1
                _audit(
                    db,
                    proc,
                    target_id=n.id,
                    action="content-to-steps",
                    meta=meta,
                    new_value={"step_ids": block_ids, "count": len(block_ids)},
                )
            n.is_active = False
            n.deleted_at = now
            deleted.append(n.id)

    # 4. 清空剩余 active 节点的 mark_status（无操作的 content 标记等）
    for n in marked:
        if n.is_active:
            n.mark_status = "unmarked"

    db.flush()
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    return ApplyMarksResult(created=created, deleted=deleted)


def _audit(
    db: Session,
    proc: Procedure,
    *,
    target_id: str,
    action: str,
    meta: RequestMeta,
    old_value: dict[str, object] | None = None,
    new_value: dict[str, object] | None = None,
) -> None:
    audit_service.log_procedure_action(
        db,
        target_id=target_id,
        procedure_group_id=proc.procedure_group_id,
        action=action,
        meta=meta,
        old_value=old_value,
        new_value=new_value,
    )
