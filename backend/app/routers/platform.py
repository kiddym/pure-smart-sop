"""平台运营端点（Phase 6）：手动设公司套餐/订阅状态。仅 is_platform_admin。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.billing.catalog import ALL_STATUSES, Plan
from app.db import get_db
from app.deps import require_platform_admin
from app.errors import not_found
from app.models.company import Company
from app.models.user import User

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


class SubscriptionUpdate(BaseModel):
    plan: str
    subscription_status: str

    @field_validator("plan")
    @classmethod
    def _valid_plan(cls, v: str) -> str:
        if v not in {p.value for p in Plan}:
            raise ValueError("无效的套餐档位")
        return v

    @field_validator("subscription_status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in ALL_STATUSES:
            raise ValueError("无效的订阅状态")
        return v


@router.patch("/companies/{company_id}/subscription")
def set_company_subscription(
    company_id: str,
    payload: SubscriptionUpdate,
    _admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    # Company 非 tenant-scoped，db.get 直取任意公司。
    company = db.get(Company, company_id)
    if company is None:
        raise not_found("COMPANY_NOT_FOUND", "公司不存在")
    company.plan = payload.plan
    company.subscription_status = payload.subscription_status
    db.commit()
    return {"plan": company.plan, "subscription_status": company.subscription_status}
