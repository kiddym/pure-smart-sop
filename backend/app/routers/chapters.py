"""章节 / 内容节点路由（api-specification §5.4）。

静态子路径（batch-content-to-steps）须在 `/{chapter_id}` 之前声明。
编辑器主保存走 PUT /procedures/{id}（整批脏节点）；本组为细粒度 action API。Router 提交事务。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.deps import RequestMeta, get_db, get_request_meta
from pydantic import BaseModel, Field

from app.schemas.node import (
    ChapterCreate,
    ChapterMoveIn,
    ChapterOut,
    ChapterUpdate,
    ConversionResult,
    MarkStatusIn,
)


class BatchContentToStepsIn(BaseModel):
    """批量 content-to-steps（原子，body: chapter_ids）。TODO A8: 端点将移除。"""

    chapter_ids: list[str] = Field(min_length=1, max_length=100)
from app.services import chapter_service, conversion_service, mark_service

router = APIRouter(prefix="/api/v1/chapters", tags=["chapters"])


@router.get("", response_model=list[ChapterOut])
def list_chapters(
    db: Session = Depends(get_db),
    procedure_id: str | None = None,
    parent_id: str | None = None,
    content_type: str | None = None,
    mark_status: str | None = None,
) -> list[ChapterOut]:
    rows = chapter_service.list_chapters(
        db,
        procedure_id=procedure_id,
        parent_id=parent_id,
        content_type=content_type,
        mark_status=mark_status,
    )
    return [ChapterOut.model_validate(r) for r in rows]


@router.post("/batch-content-to-steps", response_model=ConversionResult)
def batch_content_to_steps(
    payload: BatchContentToStepsIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ConversionResult:
    result = conversion_service.batch_content_to_steps(db, payload.chapter_ids, meta)
    db.commit()
    return result


@router.get("/{chapter_id}", response_model=ChapterOut)
def get_chapter(chapter_id: str, db: Session = Depends(get_db)) -> ChapterOut:
    return ChapterOut.model_validate(chapter_service.get_chapter(db, chapter_id))


@router.post("", response_model=ChapterOut, status_code=status.HTTP_201_CREATED)
def create_chapter(
    payload: ChapterCreate,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ChapterOut:
    ch = chapter_service.create_chapter(db, payload, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.put("/{chapter_id}", response_model=ChapterOut)
def update_chapter(
    chapter_id: str,
    payload: ChapterUpdate,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ChapterOut:
    ch = chapter_service.update_chapter(db, chapter_id, payload, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.delete("/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(
    chapter_id: str,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    chapter_service.delete_chapter(db, chapter_id, meta)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{chapter_id}/move-up", response_model=ChapterOut)
def move_up(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ChapterOut:
    ch = chapter_service.move_up(db, chapter_id, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.post("/{chapter_id}/move-down", response_model=ChapterOut)
def move_down(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ChapterOut:
    ch = chapter_service.move_down(db, chapter_id, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.post("/{chapter_id}/move", response_model=ChapterOut)
def move_chapter(
    chapter_id: str,
    payload: ChapterMoveIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ChapterOut:
    ch = chapter_service.move_chapter(db, chapter_id, payload, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.post("/{chapter_id}/toggle-skip-numbering", response_model=ChapterOut)
def toggle_skip(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ChapterOut:
    ch = chapter_service.toggle_skip_numbering(db, chapter_id, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.post("/{chapter_id}/mark-status", response_model=ChapterOut)
def set_mark_status(
    chapter_id: str,
    payload: MarkStatusIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ChapterOut:
    ch = mark_service.set_mark_status(db, chapter_id, payload.mark_status, meta)
    db.commit()
    return ChapterOut.model_validate(ch)


@router.post("/{chapter_id}/convert-to-step", response_model=ConversionResult)
def convert_to_step(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ConversionResult:
    result = conversion_service.convert_to_step(db, chapter_id, meta)
    db.commit()
    return result


@router.post("/{chapter_id}/convert-root-to-step", response_model=ConversionResult)
def convert_root_to_step(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ConversionResult:
    result = conversion_service.convert_root_to_step(db, chapter_id, meta)
    db.commit()
    return result


@router.post("/{chapter_id}/content-to-steps", response_model=ConversionResult)
def content_to_steps(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ConversionResult:
    result = conversion_service.content_to_steps(db, chapter_id, meta)
    db.commit()
    return result


@router.post("/{chapter_id}/convert-to-content")
def convert_to_content(
    chapter_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ConversionResult:
    # §19 后废弃：恒返 410 CONVERT_TO_CONTENT_DEPRECATED
    return conversion_service.convert_to_content(db, chapter_id, meta)
