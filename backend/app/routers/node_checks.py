"""核查点路由。Router 提交事务（与 nodes 路由一致）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.billing.catalog import Feature
from app.deps import get_db, require_feature
from app.schemas.node_check import CheckCreateIn, CheckOut, CheckPatchIn
from app.services import node_check_service

router = APIRouter(
    tags=["node-checks"],
    dependencies=[Depends(require_feature(Feature.sop))],
)


@router.get("/api/v1/nodes/{node_id}/checks", response_model=list[CheckOut])
def list_checks(node_id: str, db: Session = Depends(get_db)) -> list[CheckOut]:
    return [CheckOut.model_validate(c) for c in node_check_service.list_checks(db, node_id)]


@router.post(
    "/api/v1/nodes/{node_id}/checks",
    response_model=CheckOut,
    status_code=status.HTTP_201_CREATED,
)
def create_check(node_id: str, payload: CheckCreateIn, db: Session = Depends(get_db)) -> CheckOut:
    c = node_check_service.create_check(db, node_id, payload.model_dump())
    db.commit()
    db.refresh(c)
    return CheckOut.model_validate(c)


@router.patch("/api/v1/checks/{check_id}", response_model=CheckOut)
def patch_check(check_id: str, payload: CheckPatchIn, db: Session = Depends(get_db)) -> CheckOut:
    c = node_check_service.patch_check(db, check_id, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(c)
    return CheckOut.model_validate(c)


@router.delete("/api/v1/checks/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_check(check_id: str, db: Session = Depends(get_db)) -> Response:
    node_check_service.delete_check(db, check_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
