"""SOP 多租户硬化：per-company 复合唯一 + NOT NULL fail-closed + create_company 不变量。

设计依据：docs/superpowers/specs/2026-06-04-sop-tenancy-hardening-design.md
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from app import tenant
from app.models.asset import ProcedureAsset
from app.models.company import Company
from app.models.field import ProcedureField


def _make_company(db: Session, slug: str) -> str:
    """直建一家 Company（不经隔离事件），返回其 id。"""
    with tenant.bypass_tenant_scope():
        co = Company(name=slug.upper(), slug=slug)
        db.add(co)
        db.flush()
    return co.id


@pytest.fixture
def two_companies(db: Session) -> Generator[tuple[str, str], None, None]:
    """两家公司，供跨租户同自然键测试。"""
    a = _make_company(db, "co-a")
    b = _make_company(db, "co-b")
    yield a, b


def test_two_tenants_same_field_key_both_succeed(
    db: Session, two_companies: tuple[str, str]
) -> None:
    """两租户各建同 key 自定义字段均成功（#3 回归）：全局唯一 → 第二条撞 IntegrityError。"""
    co_a, co_b = two_companies

    tok = tenant.set_current_company_id(co_a)
    try:
        db.add(ProcedureField(name="风险等级", key="risk_grade", field_type="text"))
        db.flush()
    finally:
        tenant.reset_current_company_id(tok)

    tok = tenant.set_current_company_id(co_b)
    try:
        db.add(ProcedureField(name="风险等级", key="risk_grade", field_type="text"))
        db.flush()
    finally:
        tenant.reset_current_company_id(tok)

    with tenant.bypass_tenant_scope():
        rows = db.query(ProcedureField).filter(ProcedureField.key == "risk_grade").all()
    assert {r.company_id for r in rows} == {co_a, co_b}


def test_two_tenants_same_asset_sha256_both_succeed(
    db: Session, two_companies: tuple[str, str]
) -> None:
    """两租户各存同 sha256 图片资源均成功（每公司各一份，放弃跨租户字节去重）。"""
    co_a, co_b = two_companies
    sha = "a" * 64

    tok = tenant.set_current_company_id(co_a)
    try:
        db.add(
            ProcedureAsset(sha256=sha, storage_path="a.png", mime_type="image/png", size_bytes=1)
        )
        db.flush()
    finally:
        tenant.reset_current_company_id(tok)

    tok = tenant.set_current_company_id(co_b)
    try:
        db.add(
            ProcedureAsset(sha256=sha, storage_path="b.png", mime_type="image/png", size_bytes=1)
        )
        db.flush()
    finally:
        tenant.reset_current_company_id(tok)

    with tenant.bypass_tenant_scope():
        rows = db.query(ProcedureAsset).filter(ProcedureAsset.sha256 == sha).all()
    assert {r.company_id for r in rows} == {co_a, co_b}
