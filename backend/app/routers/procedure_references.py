"""SOP 参考关系路由。Router 提交事务（与 nodes/checks 路由一致）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.billing.catalog import Feature
from app.deps import get_db, require_feature
from app.schemas.procedure_reference import ReferenceCreateIn, ReferenceOut, ReferencePatchIn
from app.services import procedure_reference_service

router = APIRouter(
    tags=["procedure-references"],
    dependencies=[Depends(require_feature(Feature.sop))],
)


@router.get("/api/v1/procedures/{procedure_id}/references", response_model=list[ReferenceOut])
def list_references(procedure_id: str, db: Session = Depends(get_db)) -> list[ReferenceOut]:
    rows = procedure_reference_service.list_references(db, procedure_id)
    return [ReferenceOut.model_validate(procedure_reference_service.serialize(db, r)) for r in rows]


@router.post(
    "/api/v1/procedures/{procedure_id}/references",
    response_model=ReferenceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_reference(procedure_id: str, payload: ReferenceCreateIn, db: Session = Depends(get_db)) -> ReferenceOut:
    ref = procedure_reference_service.create_reference(db, procedure_id, payload.model_dump())
    db.commit()
    db.refresh(ref)
    return ReferenceOut.model_validate(procedure_reference_service.serialize(db, ref))


@router.patch("/api/v1/references/{reference_id}", response_model=ReferenceOut)
def patch_reference(reference_id: str, payload: ReferencePatchIn, db: Session = Depends(get_db)) -> ReferenceOut:
    ref = procedure_reference_service.patch_reference(db, reference_id, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(ref)
    return ReferenceOut.model_validate(procedure_reference_service.serialize(db, ref))


@router.delete("/api/v1/references/{reference_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reference(reference_id: str, db: Session = Depends(get_db)) -> Response:
    procedure_reference_service.delete_reference(db, reference_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
