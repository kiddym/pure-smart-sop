"""步骤路由（api-specification §5.4）。细粒度 action API；编辑器主保存走 PUT /procedures/{id}。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.deps import RequestMeta, get_db, get_request_meta
from app.schemas.node import (
    ConversionResult,
    StepCreate,
    StepMoveIn,
    StepOut,
    StepUpdate,
)
from app.services import conversion_service, step_service

router = APIRouter(prefix="/api/v1/steps", tags=["steps"])


@router.get("", response_model=list[StepOut])
def list_steps(
    db: Session = Depends(get_db),
    procedure_id: str | None = None,
    chapter_id: str | None = None,
) -> list[StepOut]:
    rows = step_service.list_steps(db, procedure_id=procedure_id, chapter_id=chapter_id)
    return [StepOut.model_validate(r) for r in rows]


@router.get("/{step_id}", response_model=StepOut)
def get_step(step_id: str, db: Session = Depends(get_db)) -> StepOut:
    return StepOut.model_validate(step_service.get_step(db, step_id))


@router.post("", response_model=StepOut, status_code=status.HTTP_201_CREATED)
def create_step(
    payload: StepCreate,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> StepOut:
    st = step_service.create_step(db, payload, meta)
    db.commit()
    return StepOut.model_validate(st)


@router.put("/{step_id}", response_model=StepOut)
def update_step(
    step_id: str,
    payload: StepUpdate,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> StepOut:
    st = step_service.update_step(db, step_id, payload, meta)
    db.commit()
    return StepOut.model_validate(st)


@router.delete("/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_step(
    step_id: str,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    step_service.delete_step(db, step_id, meta)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{step_id}/move-up", response_model=StepOut)
def move_up(
    step_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> StepOut:
    st = step_service.move_up(db, step_id, meta)
    db.commit()
    return StepOut.model_validate(st)


@router.post("/{step_id}/move-down", response_model=StepOut)
def move_down(
    step_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> StepOut:
    st = step_service.move_down(db, step_id, meta)
    db.commit()
    return StepOut.model_validate(st)


@router.post("/{step_id}/move", response_model=StepOut)
def move_step(
    step_id: str,
    payload: StepMoveIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> StepOut:
    st = step_service.move_step(db, step_id, payload, meta)
    db.commit()
    return StepOut.model_validate(st)


@router.post("/{step_id}/toggle-skip-numbering", response_model=StepOut)
def toggle_skip(
    step_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> StepOut:
    st = step_service.toggle_skip_numbering(db, step_id, meta)
    db.commit()
    return StepOut.model_validate(st)


@router.post("/{step_id}/convert-to-chapter", response_model=ConversionResult)
def convert_to_chapter(
    step_id: str, db: Session = Depends(get_db), meta: RequestMeta = Depends(get_request_meta)
) -> ConversionResult:
    result = conversion_service.convert_to_chapter(db, step_id, meta)
    db.commit()
    return result
