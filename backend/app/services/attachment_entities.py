"""通用附件的实体注册表 + 解析授权（多态权限随 entity_type 动态）。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import tenant
from app.deps import user_permission_codes
from app.errors import bad_request, forbidden, not_found
from app.models.procedure import Procedure
from app.models.user import User
from app.services import attachment_hooks as hooks


@dataclass(frozen=True)
class EntitySpec:
    model: type[Any]
    view_perm: str | None
    edit_perm: str | None
    scoped: bool  # True=租户作用域查询；False=bypass（procedure 容忍 company_id NULL）
    write_guard: Callable[[Any], None] | None = None


ENTITY_REGISTRY: dict[str, EntitySpec] = {
    "procedure": EntitySpec(
        Procedure, None, None, scoped=False, write_guard=hooks.procedure_write_guard
    ),
}


def get_spec(entity_type: str) -> EntitySpec:
    spec = ENTITY_REGISTRY.get(entity_type)
    if spec is None:
        raise bad_request("INVALID_ENTITY_TYPE", "不支持的附件实体类型", field="entity_type")
    return spec


def _lookup_host(db: Session, spec: EntitySpec, entity_id: str) -> Any:
    stmt = select(spec.model).where(
        spec.model.id == entity_id,
        spec.model.is_active.is_(True),
    )
    if spec.scoped:
        host = db.execute(stmt).scalar_one_or_none()
    else:
        with tenant.bypass_tenant_scope():
            host = db.execute(stmt).scalar_one_or_none()
    if host is None:
        raise not_found("NOT_FOUND", "目标对象不存在")
    return host


def resolve_and_authorize(
    db: Session,
    user: User | None,
    entity_type: str,
    entity_id: str,
    action: Literal["read", "write"],
) -> Any:
    """校验 entity_type（未知→400）→查宿主（不存在/跨租户→404）→租户归属校验→授权（不足→403）→write_guard。返回宿主。"""
    spec = get_spec(entity_type)
    host = _lookup_host(db, spec, entity_id)
    # 跨租户归属校验：宿主走 bypass 查回（scoped=False），故此处显式比对 company_id，
    # 防止认证用户凭 id 访问他公司宿主下的附件（审计 #2）。宿主 company_id 为 NULL
    # 的 phase-0 无主程序不参与比对（保持既有容忍）。
    host_company_id = getattr(host, "company_id", None)
    if user is not None and host_company_id is not None and host_company_id != user.company_id:
        raise not_found("NOT_FOUND", "目标对象不存在")
    perm = spec.view_perm if action == "read" else spec.edit_perm
    if perm is not None and (user is None or perm not in user_permission_codes(db, user)):
        raise forbidden("FORBIDDEN", "权限不足")
    if action != "read" and spec.write_guard is not None:
        spec.write_guard(host)
    return host
