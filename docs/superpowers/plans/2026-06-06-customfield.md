# 业务实体动态自定义字段（CustomField）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理员为 5 个业务实体（work_order/asset/request/location/part）动态定义自定义字段，并在各实体表单录入、详情展示其值。

**Architecture:** 方案 A——多态 `CustomFieldDef` 定义表 + 各宿主实体 `custom_values` JSON 值列 + 从 SOP `field_service` 抽取共享值校验模块 `field_validation`。值仅录入展示、不筛选；复用基础类型集；与 SOP `ProcedureField` 解耦。详见 `docs/superpowers/specs/2026-06-06-customfield-design.md`。

**Tech Stack:** 后端 FastAPI + SQLAlchemy + Alembic（venv 在 `backend/.venv`）；前端 Vue3 + TS + Element Plus + Pinia + vitest。

**全局门禁（每个 Task 的提交前都要满足）：**
- 后端：`cd backend && .venv/bin/python -m pytest <相关测试> -q` 绿；改了模型/迁移则 `.venv/bin/alembic heads` 单 head + 重放（`rm -f /tmp/cf.db && DATABASE_URL="sqlite:////tmp/cf.db" .venv/bin/alembic upgrade head && downgrade -1 && upgrade head`）；`.venv/bin/python -c "import app.main"`；`.venv/bin/ruff check app tests`；`.venv/bin/ruff format --check app`；`.venv/bin/mypy app`。
- 前端：`cd frontend && npx vue-tsc --noEmit`；`npx eslint <改动文件>`；`npx vitest run <相关 spec>`。
- 净室红线：全新原创，不复制 Atlas 代码/命名。

---

## 文件结构（先锁定边界）

**后端 新建：**
- `app/services/field_validation.py` — 共享值校验（duck-typed 于任何含 `key/name/field_type/validation_rules/options` 的字段定义对象）
- `app/models/custom_field_def.py` — `CustomFieldDef` 多态定义模型
- `app/schemas/custom_field.py` — 定义 CRUD schema
- `app/services/custom_field_service.py` — 定义 CRUD + `entity_type` 校验 + `validate_values(db, entity_type, custom_values)`
- `app/routers/custom_fields.py` — `/api/v1/custom-fields` 路由
- `alembic/versions/20260606_0018_custom_field.py` — 建表 + 5 宿主列迁移
- `tests/integration/test_custom_fields_api.py`、`tests/unit/test_field_validation.py`、`tests/integration/test_custom_values_on_entities.py`

**后端 修改：**
- `app/services/field_service.py` — `validate_values` 改为委托共享模块（行为不变）
- `app/models/__init__.py` — 注册 `CustomFieldDef`
- `app/main.py` — 注册 `custom_fields` router
- 5 宿主模型加 `custom_values` 列：`app/models/work_order.py`、`maintenance_asset.py`、`request.py`、`location.py`、`part.py`
- 5 宿主 schema 加 `custom_values`：`app/schemas/work_order.py`、`asset.py`、`request.py`、`location.py`、`part.py`
- 5 宿主 service 接线：`app/services/work_order_service.py`、`maintenance_asset_service.py`、`request_service.py`、`location_service.py`、`part_service.py`

**前端 新建：**
- `src/api/customFields.ts`、`src/types/customField.ts`
- `src/views/settings/CustomFieldsView.vue`（定义管理页）
- `src/components/CustomFieldsSection.vue`（可复用录入/展示区）
- `tests/unit/CustomFieldsView.spec.ts`、`tests/unit/CustomFieldsSection.spec.ts`

**前端 修改：**
- `src/router/routes.ts`（`/admin/custom-fields`）、`src/components/AppSidebar.vue`（入口）
- 5 实体表单与详情接入 `CustomFieldsSection`（具体见 Phase 5）

---

## Phase 1：抽取共享值校验模块（不改 SOP 行为）

### Task 1：建立 `field_validation` 共享模块并让 `field_service` 委托它

**Files:**
- Create: `backend/app/services/field_validation.py`
- Create: `backend/tests/unit/test_field_validation.py`
- Modify: `backend/app/services/field_service.py`（`_is_empty`/`_err`/`_option_values`/`_validate_one`/`validate_values` 收敛到委托）

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_field_validation.py`

```python
"""共享字段值校验（duck-typed 于任意字段定义对象）。"""

from dataclasses import dataclass, field as dc_field
from typing import Any

import pytest

from app.errors import APIError
from app.services import field_validation as fv


@dataclass
class FakeDef:
    key: str
    name: str
    field_type: str
    required: bool = False
    validation_rules: dict[str, Any] = dc_field(default_factory=dict)
    options: list[dict[str, Any]] = dc_field(default_factory=list)


def test_text_min_length_violation_raises():
    defs = [FakeDef(key="note", name="备注", field_type="text", validation_rules={"minLength": 3})]
    with pytest.raises(APIError):
        fv.validate_against_definitions(defs, {"note": "ab"}, require_check=False)


def test_required_missing_raises_when_require_check():
    defs = [FakeDef(key="note", name="备注", field_type="text", required=True)]
    with pytest.raises(APIError):
        fv.validate_against_definitions(defs, {}, require_check=True)


def test_required_missing_ok_when_not_require_check():
    defs = [FakeDef(key="note", name="备注", field_type="text", required=True)]
    fv.validate_against_definitions(defs, {}, require_check=False)  # no raise


def test_select_value_not_in_options_raises():
    defs = [FakeDef(key="c", name="颜色", field_type="select", options=[{"value": "red"}])]
    with pytest.raises(APIError):
        fv.validate_against_definitions(defs, {"c": "blue"}, require_check=False)


def test_unknown_key_ignored_by_shared_validator():
    # 共享校验器对未知键容忍（SOP 行为）；未知键拒绝是 CustomField 上层的额外检查。
    defs = [FakeDef(key="note", name="备注", field_type="text")]
    fv.validate_against_definitions(defs, {"ghost": "x"}, require_check=False)  # no raise
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_field_validation.py -q`
Expected: FAIL（`ModuleNotFoundError: app.services.field_validation` 或 `AttributeError: validate_against_definitions`）

- [ ] **Step 3: 写 `field_validation.py`**（把 field_service 的纯校验逻辑搬来，duck-typed）

```python
"""共享自定义字段值校验。

不依赖具体 ORM 模型——只要字段定义对象有 key/name/field_type/validation_rules/
options 属性即可（ProcedureField 与 CustomFieldDef 均满足）。未知键容忍（不报错）；
required 仅在 require_check=True 时强制。
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Protocol, Sequence

from app.errors import unprocessable

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FieldDef(Protocol):
    key: str
    name: str
    field_type: str
    required: bool
    validation_rules: dict[str, Any]
    options: list[dict[str, Any]]


def _is_empty(val: Any) -> bool:
    return val is None or val == "" or val == []


def _err(field: FieldDef, msg: str) -> None:
    raise unprocessable("CUSTOM_FIELD_INVALID", f"字段「{field.name}」{msg}", field=field.key)


def _option_values(field: FieldDef) -> set[str]:
    return {str(o.get("value")) for o in (field.options or [])}


def validate_one(field: FieldDef, val: Any) -> None:
    schema = field.validation_rules or {}
    ftype = field.field_type
    if ftype in ("text", "textarea"):
        if not isinstance(val, str):
            _err(field, "应为文本")
        if "minLength" in schema and len(val) < schema["minLength"]:
            _err(field, f"长度不足 {schema['minLength']}")
        if "maxLength" in schema and len(val) > schema["maxLength"]:
            _err(field, f"长度超过 {schema['maxLength']}")
        if "pattern" in schema and re.search(schema["pattern"], val) is None:
            _err(field, "格式不符合要求")
    elif ftype == "number":
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            _err(field, "应为数字")
        if "minimum" in schema and val < schema["minimum"]:
            _err(field, f"不能小于 {schema['minimum']}")
        if "maximum" in schema and val > schema["maximum"]:
            _err(field, f"不能大于 {schema['maximum']}")
    elif ftype == "date":
        if not isinstance(val, str) or _DATE_RE.match(val) is None:
            _err(field, "应为 YYYY-MM-DD 日期")
        try:
            dt.date.fromisoformat(val)
        except ValueError:
            _err(field, "日期无效")
    elif ftype == "select":
        if val not in _option_values(field):
            _err(field, "不在可选项内")
    elif ftype in ("multi_select", "checkbox"):
        if not isinstance(val, list):
            _err(field, "应为多选列表")
        opts = _option_values(field)
        for item in val:
            if item not in opts:
                _err(field, "含无效选项")


def validate_against_definitions(
    fields: Sequence[FieldDef], custom_values: dict[str, Any], *, require_check: bool
) -> None:
    for field in fields:
        present = field.key in custom_values and not _is_empty(custom_values[field.key])
        if field.required and require_check and not present:
            _err(field, "为必填项，请填写")
        if present:
            validate_one(field, custom_values[field.key])
```

- [ ] **Step 4: 让 `field_service.validate_values` 委托共享模块**（删掉 `_is_empty`/`_err`/`_option_values`/`_validate_one` 的本地副本，改 import）

在 `backend/app/services/field_service.py`：删除本地 `_is_empty`、`_err`、`_option_values`、`_validate_one` 四个函数，并把 `validate_values` 改为：

```python
from app.services import field_validation as fv

def validate_values(db: Session, custom_values: dict[str, Any], *, require_check: bool) -> None:
    fields = list(
        db.execute(
            select(ProcedureField).where(
                ProcedureField.is_active.is_(True), ProcedureField.status == "active"
            )
        ).scalars()
    )
    fv.validate_against_definitions(fields, custom_values, require_check=require_check)
```

（`_DATE_RE` 若 field_service 其它处未用则一并删除；`compile_form_to_schema` 保留不动。）

- [ ] **Step 5: 跑新测试 + SOP 回归**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/test_field_validation.py tests/ -k "field or procedure or custom_values" -q`
Expected: PASS（新单测全过；既有 SOP 字段/程序测试不破）

- [ ] **Step 6: 门禁 + 提交**

Run: `cd backend && .venv/bin/ruff check app tests && .venv/bin/ruff format app tests && .venv/bin/mypy app && .venv/bin/python -c "import app.main"`

```bash
git add backend/app/services/field_validation.py backend/app/services/field_service.py backend/tests/unit/test_field_validation.py
git commit -m "refactor(cf): 抽取共享字段值校验 field_validation，field_service 委托之（行为不变）"
```

---

## Phase 2：定义表 + 迁移 + 管理 API

### Task 2：`CustomFieldDef` 模型 + 注册

**Files:**
- Create: `backend/app/models/custom_field_def.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 写模型** `backend/app/models/custom_field_def.py`

```python
"""业务实体动态自定义字段定义（多态 entity_type）。与 SOP ProcedureField 解耦。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, UUIDMixin


class CustomFieldDef(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_custom_field_def"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "entity_type", "key", name="uq_custom_field_def_company_entity_key"
        ),
    )

    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    field_type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
    required: Mapped[bool] = mapped_column(default=False, server_default="0")
    default_value: Mapped[Any | None] = mapped_column(JSON, default=None, nullable=True)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    validation_rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
```

- [ ] **Step 2: 注册到 `__init__.py`**

在 `backend/app/models/__init__.py`：import 行（按字母序，约在 `custom`/`currency` 后）加 `from app.models.custom_field_def import CustomFieldDef`；`__all__` 加 `"CustomFieldDef"`（字母序）。

- [ ] **Step 3: 验证可导入**

Run: `cd backend && .venv/bin/python -c "from app.models import CustomFieldDef; print('ok')"`
Expected: `ok`

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/custom_field_def.py backend/app/models/__init__.py
git commit -m "feat(cf): CustomFieldDef 多态定义模型 + 注册"
```

### Task 3：迁移（建定义表 + 5 宿主 custom_values 列）

**Files:**
- Create: `backend/alembic/versions/20260606_0018_custom_field.py`

- [ ] **Step 1: 写迁移**（down_revision 取当前单 head；先确认）

先 `cd backend && .venv/bin/alembic heads` 确认当前 head（预期 `push_switch_verify`），写入 down_revision。

```python
"""custom field def table + 5 host custom_values columns

Revision ID: custom_field
Revises: push_switch_verify
Create Date: 2026-06-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "custom_field"
down_revision: str | Sequence[str] | None = "push_switch_verify"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HOSTS = ("tb_work_order", "tb_asset", "tb_request", "tb_location", "tb_part")


def upgrade() -> None:
    op.create_table(
        "tb_custom_field_def",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("field_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("default_value", sa.JSON(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("validation_rules", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.UniqueConstraint(
            "company_id", "entity_type", "key", name="uq_custom_field_def_company_entity_key"
        ),
    )
    op.create_index("ix_tb_custom_field_def_company_id", "tb_custom_field_def", ["company_id"])
    op.create_index("ix_tb_custom_field_def_entity_type", "tb_custom_field_def", ["entity_type"])
    for tbl in _HOSTS:
        with op.batch_alter_table(tbl) as batch_op:
            batch_op.add_column(
                sa.Column("custom_values", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
            )


def downgrade() -> None:
    for tbl in _HOSTS:
        with op.batch_alter_table(tbl) as batch_op:
            batch_op.drop_column("custom_values")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_custom_field_def_entity_type", table_name="tb_custom_field_def")
        op.drop_index("ix_tb_custom_field_def_company_id", table_name="tb_custom_field_def")
    op.drop_table("tb_custom_field_def")
```

> 注：`is_active`/`deleted_at` 来自 SoftDeleteMixin，须显式建列（参考既有带 SoftDeleteMixin 的表迁移，如 tb_procedure_field 的建表迁移；若该 mixin 列名/类型不同，以 `grep -rn "is_active\|deleted_at" alembic/versions/ | head` 核对既有写法为准）。

- [ ] **Step 2: 校验单 head + 重放**

Run:
```
cd backend && .venv/bin/alembic heads
rm -f /tmp/cf.db && DATABASE_URL="sqlite:////tmp/cf.db" .venv/bin/alembic upgrade head && DATABASE_URL="sqlite:////tmp/cf.db" .venv/bin/alembic downgrade -1 && DATABASE_URL="sqlite:////tmp/cf.db" .venv/bin/alembic upgrade head && rm -f /tmp/cf.db
```
Expected: 单 head `custom_field`；重放无错。

- [ ] **Step 3: 提交**

```bash
git add backend/alembic/versions/20260606_0018_custom_field.py
git commit -m "feat(cf): 迁移 custom_field 建定义表 + 5 宿主 custom_values 列"
```

### Task 4：定义 CRUD schema + service + 路由

**Files:**
- Create: `backend/app/schemas/custom_field.py`, `backend/app/services/custom_field_service.py`, `backend/app/routers/custom_fields.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_custom_fields_api.py`

- [ ] **Step 1: 写 schema** `backend/app/schemas/custom_field.py`

```python
"""业务实体自定义字段定义 schema。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ENTITY_TYPES = ("work_order", "asset", "request", "location", "part")
FIELD_TYPES = ("text", "number", "date", "select", "multi_select", "checkbox", "textarea")


class CustomFieldOption(BaseModel):
    value: str
    label: str = ""
    archived: bool = False


class CustomFieldValidation(BaseModel):
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None


class CustomFieldCreate(BaseModel):
    entity_type: Literal["work_order", "asset", "request", "location", "part"]
    key: str = Field(max_length=100)
    name: str = Field(min_length=1, max_length=100)
    field_type: Literal[
        "text", "number", "date", "select", "multi_select", "checkbox", "textarea"
    ]
    description: str = ""
    required: bool = False
    default_value: Any | None = None
    options: list[CustomFieldOption] = []
    validation: CustomFieldValidation = CustomFieldValidation()
    sort_order: int = 0


class CustomFieldUpdate(BaseModel):
    # key / entity_type 不可改，不在此出现
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    required: bool = False
    default_value: Any | None = None
    options: list[CustomFieldOption] = []
    validation: CustomFieldValidation = CustomFieldValidation()
    sort_order: int = 0


class CustomFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_type: str
    key: str
    name: str
    field_type: str
    description: str
    required: bool
    default_value: Any | None
    options: list[dict[str, Any]]
    sort_order: int
    status: str
```

- [ ] **Step 2: 写 service** `backend/app/services/custom_field_service.py`

```python
"""业务实体自定义字段定义 CRUD + 值校验入口。"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request, conflict, not_found, unprocessable
from app.models.base import utcnow
from app.models.custom_field_def import CustomFieldDef
from app.schemas.custom_field import (
    ENTITY_TYPES,
    CustomFieldCreate,
    CustomFieldUpdate,
)
from app.services import field_service, field_validation as fv

KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def assert_entity(entity_type: str) -> None:
    if entity_type not in ENTITY_TYPES:
        raise bad_request("INVALID_ENTITY_TYPE", "不支持的实体类型", field="entity_type")


def _active_defs(db: Session, entity_type: str, *, only_active_status: bool) -> list[CustomFieldDef]:
    q = select(CustomFieldDef).where(
        CustomFieldDef.is_active.is_(True), CustomFieldDef.entity_type == entity_type
    )
    if only_active_status:
        q = q.where(CustomFieldDef.status == "active")
    return list(db.execute(q.order_by(CustomFieldDef.sort_order, CustomFieldDef.created_at)).scalars())


def list_defs(db: Session, entity_type: str, *, include_archived: bool) -> list[CustomFieldDef]:
    assert_entity(entity_type)
    return _active_defs(db, entity_type, only_active_status=not include_archived)


def get_or_404(db: Session, field_id: str) -> CustomFieldDef:
    row = db.execute(
        select(CustomFieldDef).where(
            CustomFieldDef.id == field_id, CustomFieldDef.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if row is None:
        raise not_found("NOT_FOUND", "自定义字段不存在")
    return row


def create(db: Session, payload: CustomFieldCreate) -> CustomFieldDef:
    assert_entity(payload.entity_type)
    if KEY_RE.match(payload.key) is None:
        raise unprocessable("VALIDATION_FAILED", "key 须为小写字母开头的字母/数字/下划线", field="key")
    dup = db.execute(
        select(CustomFieldDef.id).where(
            CustomFieldDef.is_active.is_(True),
            CustomFieldDef.entity_type == payload.entity_type,
            CustomFieldDef.key == payload.key,
        )
    ).first()
    if dup is not None:
        raise conflict("FIELD_KEY_DUPLICATE", "该实体下字段 key 已存在", field="key")
    row = CustomFieldDef(
        entity_type=payload.entity_type,
        key=payload.key,
        name=payload.name,
        field_type=payload.field_type,
        description=payload.description,
        required=payload.required,
        default_value=payload.default_value,
        options=[o.model_dump() for o in payload.options],
        validation_rules=field_service.compile_form_to_schema(
            payload.field_type,
            # 复用 SOP 的 compile（入参鸭子类型：含 min_length/max_length/pattern/minimum/maximum）
            payload.validation,  # type: ignore[arg-type]
        ),
        sort_order=payload.sort_order,
        status="active",
    )
    db.add(row)
    db.flush()
    return row


def update(db: Session, field_id: str, payload: CustomFieldUpdate) -> CustomFieldDef:
    row = get_or_404(db, field_id)
    row.name = payload.name
    row.description = payload.description
    row.required = payload.required
    row.default_value = payload.default_value
    row.options = field_service._merge_options(row.options, payload.options)  # 软归档旧选项
    row.validation_rules = field_service.compile_form_to_schema(row.field_type, payload.validation)  # type: ignore[arg-type]
    row.sort_order = payload.sort_order
    db.flush()
    return row


def set_status(db: Session, field_id: str, status: str) -> CustomFieldDef:
    row = get_or_404(db, field_id)
    row.status = status
    db.flush()
    return row


def delete(db: Session, field_id: str) -> None:
    row = get_or_404(db, field_id)
    row.is_active = False
    row.deleted_at = utcnow()
    db.flush()


def reorder(db: Session, entity_type: str, ordered_ids: list[str]) -> list[CustomFieldDef]:
    assert_entity(entity_type)
    rows = {
        r.id: r
        for r in db.execute(
            select(CustomFieldDef).where(
                CustomFieldDef.id.in_(ordered_ids),
                CustomFieldDef.is_active.is_(True),
                CustomFieldDef.entity_type == entity_type,
            )
        ).scalars()
    }
    order = 0
    for fid in ordered_ids:
        r = rows.get(fid)
        if r is not None:
            r.sort_order = order
            order += 1
    db.flush()
    return list_defs(db, entity_type, include_archived=False)


def validate_values(db: Session, entity_type: str, custom_values: dict[str, Any]) -> None:
    """写宿主前调用：按 entity_type 的 active 定义校验；未知 key（无任何定义）拒绝 422。"""
    assert_entity(entity_type)
    all_defs = _active_defs(db, entity_type, only_active_status=False)  # active + archived
    known = {d.key for d in all_defs}
    unknown = [k for k in custom_values if k not in known]
    if unknown:
        raise unprocessable("UNKNOWN_CUSTOM_FIELD", f"未知自定义字段: {', '.join(unknown)}")
    active = [d for d in all_defs if d.status == "active"]
    fv.validate_against_definitions(active, custom_values, require_check=True)
```

> 注：`field_service._merge_options` 与 `compile_form_to_schema` 为复用；若不愿用下划线私有，Task 1 可顺带把 `_merge_options` 提为公开 `merge_options`（二选一，保持一致并在提交信息注明）。`compile_form_to_schema` 入参是 `FieldValidation`，而这里传 `CustomFieldValidation`——二者字段同名，鸭子类型可用；为类型干净可在 schema 让 `CustomFieldValidation` 直接复用 `FieldValidation`（import 之），避免 `# type: ignore`。**实现时优先后者：`from app.schemas.field import FieldValidation as CustomFieldValidation`**。

- [ ] **Step 3: 写路由** `backend/app/routers/custom_fields.py`

```python
"""业务实体自定义字段定义 API（/api/v1/custom-fields）。读=任意认证，写=company.settings。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_current_user, get_db, require_permission
from app.models.custom_field_def import CustomFieldDef
from app.models.user import User
from app.schemas.custom_field import CustomFieldCreate, CustomFieldOut, CustomFieldUpdate
from app.services import custom_field_service as svc

router = APIRouter(prefix="/api/v1/custom-fields", tags=["custom-fields"])


@router.get("", response_model=list[CustomFieldOut])
def list_fields(
    entity_type: str,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CustomFieldDef]:
    return svc.list_defs(db, entity_type, include_archived=include_archived)


@router.post("", response_model=CustomFieldOut, status_code=status.HTTP_201_CREATED)
def create_field(
    payload: CustomFieldCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> CustomFieldDef:
    row = svc.create(db, payload)
    db.commit()
    return row


@router.patch("/{field_id}", response_model=CustomFieldOut)
def update_field(
    field_id: str,
    payload: CustomFieldUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> CustomFieldDef:
    row = svc.update(db, field_id, payload)
    db.commit()
    return row


@router.patch("/{field_id}/archive", response_model=CustomFieldOut)
def archive_field(
    field_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> CustomFieldDef:
    row = svc.set_status(db, field_id, "archived")
    db.commit()
    return row


@router.patch("/{field_id}/restore", response_model=CustomFieldOut)
def restore_field(
    field_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> CustomFieldDef:
    row = svc.set_status(db, field_id, "active")
    db.commit()
    return row


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_field(
    field_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> None:
    svc.delete(db, field_id)
    db.commit()


@router.post("/reorder", response_model=list[CustomFieldOut])
def reorder_fields(
    entity_type: str,
    ordered_ids: list[str],
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(permissions.COMPANY_SETTINGS)),
) -> list[CustomFieldDef]:
    rows = svc.reorder(db, entity_type, ordered_ids)
    db.commit()
    return rows
```

- [ ] **Step 4: 注册路由** 在 `backend/app/main.py`：import 块加 `custom_fields`（字母序，约在 `currencies`/`customers` 附近），并在 include 区加 `app.include_router(custom_fields.router)`。

- [ ] **Step 5: 写集成测试** `backend/tests/integration/test_custom_fields_api.py`

```python
def _admin(client, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "A"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _create(client, h, **over):
    body = {"entity_type": "work_order", "key": "severity", "name": "严重度", "field_type": "select",
            "options": [{"value": "high", "label": "高"}, {"value": "low", "label": "低"}]}
    body.update(over)
    return client.post("/api/v1/custom-fields", headers=h, json=body)


def test_create_and_list(client):
    h = _h(_admin(client))
    r = _create(client, h)
    assert r.status_code == 201, r.text
    rows = client.get("/api/v1/custom-fields?entity_type=work_order", headers=h).json()
    assert [x["key"] for x in rows] == ["severity"]


def test_key_immutable_via_no_field(client):
    h = _h(_admin(client))
    fid = _create(client, h).json()["id"]
    # PATCH 不接受 key 字段，改名生效但 key 不变
    r = client.patch(f"/api/v1/custom-fields/{fid}", headers=h,
                     json={"name": "Severity2", "field_type": "select",
                           "options": [{"value": "high"}]})
    assert r.status_code == 200
    assert client.get("/api/v1/custom-fields?entity_type=work_order", headers=h).json()[0]["key"] == "severity"


def test_bad_key_422(client):
    h = _h(_admin(client))
    assert _create(client, h, key="Bad Key", field_type="text", options=[]).status_code == 422


def test_dup_key_conflict(client):
    h = _h(_admin(client))
    _create(client, h, field_type="text", options=[])
    assert _create(client, h, field_type="text", options=[]).status_code == 409


def test_unknown_entity_type_rejected(client):
    h = _h(_admin(client))
    assert client.get("/api/v1/custom-fields?entity_type=bogus", headers=h).status_code == 400


def test_archive_excludes_from_active_list(client):
    h = _h(_admin(client))
    fid = _create(client, h, field_type="text", options=[]).json()["id"]
    client.patch(f"/api/v1/custom-fields/{fid}/archive", headers=h)
    assert client.get("/api/v1/custom-fields?entity_type=work_order", headers=h).json() == []
    assert len(client.get("/api/v1/custom-fields?entity_type=work_order&include_archived=true", headers=h).json()) == 1


def test_write_requires_company_settings(client, db):
    from sqlalchemy import select
    from app import tenant
    from app.models.user import User
    from app.services import invitation_service
    client.post("/api/v1/auth/register", json={"company_name": "Acme", "email": "admin@acme.com",
                "password": "secret123", "name": "Admin"})
    with tenant.bypass_tenant_scope():
        admin = db.execute(select(User).where(User.email == "admin@acme.com")).scalar_one()
    _inv, raw = invitation_service.invite(db, company_id=admin.company_id, email="m@acme.com",
                                          role_id=None, invited_by=admin.id)
    db.commit()
    tok = client.post("/api/v1/auth/accept-invite",
                      json={"token": raw, "name": "M", "password": "memberpw1"}).json()["access_token"]
    h = _h(tok)
    assert client.get("/api/v1/custom-fields?entity_type=work_order", headers=h).status_code == 200
    assert _create(client, h, field_type="text", options=[]).status_code == 403


def test_tenant_isolation(client):
    hA = _h(_admin(client, "CoA", "a@a.com"))
    hB = _h(_admin(client, "CoB", "b@b.com"))
    _create(client, hA, field_type="text", options=[])
    assert client.get("/api/v1/custom-fields?entity_type=work_order", headers=hB).json() == []
```

- [ ] **Step 6: 跑测试 + 门禁 + 提交**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_custom_fields_api.py -q` → PASS
Run 门禁：`.venv/bin/python -c "import app.main"; .venv/bin/ruff check app tests; .venv/bin/ruff format app tests; .venv/bin/mypy app`

```bash
git add backend/app/schemas/custom_field.py backend/app/services/custom_field_service.py backend/app/routers/custom_fields.py backend/app/main.py backend/tests/integration/test_custom_fields_api.py
git commit -m "feat(cf): 自定义字段定义 CRUD/归档/排序 API + 值校验入口"
```

---

## Phase 3：5 实体接入 custom_values 读写

> 模式：每实体 ① 模型加 `custom_values` 列（Task 3 迁移已建 DB 列，这里加 ORM 映射）② Create/Update schema 加 `custom_values: dict | None`③ Read schema 暴露 `custom_values`④ service create/update：写前调 `custom_field_service.validate_values(db, "<entity>", payload.custom_values)`，update 走 key 级合并。**注意各实体 Read 序列化方式不同**（work_order/request 直接 ORM；asset/location/part 走 `to_read` dict）——按该实体既有方式暴露 `custom_values`。

### Task 5：work_order 接入（完整模板）

**Files:** Modify `backend/app/models/work_order.py`, `backend/app/schemas/work_order.py`, `backend/app/services/work_order_service.py`; Test `backend/tests/integration/test_custom_values_on_entities.py`

- [ ] **Step 1: 写失败测试**（建到 `test_custom_values_on_entities.py`，本 Task 起逐实体追加）

```python
def _admin(client):
    return client.post("/api/v1/auth/register", json={"company_name": "Acme",
        "email": "a@acme.com", "password": "secret123", "name": "A"}).json()["access_token"]

def _h(t):
    return {"Authorization": f"Bearer {t}"}

def _def(client, h, entity_type, key="note", field_type="text", required=False, options=None):
    return client.post("/api/v1/custom-fields", headers=h, json={
        "entity_type": entity_type, "key": key, "name": key, "field_type": field_type,
        "required": required, "options": options or []}).json()

def test_work_order_custom_values_roundtrip(client):
    h = _h(_admin(client))
    _def(client, h, "work_order", key="note", field_type="text")
    wo = client.post("/api/v1/work-orders", headers=h, json={
        "title": "T", "custom_values": {"note": "hello"}})
    assert wo.status_code == 201, wo.text
    wid = wo.json()["id"]
    assert wo.json()["custom_values"] == {"note": "hello"}
    got = client.get(f"/api/v1/work-orders/{wid}", headers=h).json()
    assert got["custom_values"]["note"] == "hello"

def test_work_order_unknown_key_422(client):
    h = _h(_admin(client))
    r = client.post("/api/v1/work-orders", headers=h, json={"title": "T", "custom_values": {"ghost": 1}})
    assert r.status_code == 422

def test_work_order_required_missing_422(client):
    h = _h(_admin(client))
    _def(client, h, "work_order", key="req", field_type="text", required=True)
    r = client.post("/api/v1/work-orders", headers=h, json={"title": "T", "custom_values": {}})
    assert r.status_code == 422

def test_work_order_update_merges_preserving_archived(client):
    h = _h(_admin(client))
    _def(client, h, "work_order", key="a", field_type="text")
    d2 = _def(client, h, "work_order", key="b", field_type="text")
    wid = client.post("/api/v1/work-orders", headers=h, json={"title": "T",
        "custom_values": {"a": "1", "b": "2"}}).json()["id"]
    client.patch(f"/api/v1/custom-fields/{d2['id']}/archive", headers=h)
    # 表单只提交 active 字段 a；归档字段 b 的值应保留
    client.patch(f"/api/v1/work-orders/{wid}", headers=h, json={"custom_values": {"a": "9"}})
    got = client.get(f"/api/v1/work-orders/{wid}", headers=h).json()["custom_values"]
    assert got == {"a": "9", "b": "2"}
```

- [ ] **Step 2: 跑测试确认失败** `cd backend && .venv/bin/python -m pytest tests/integration/test_custom_values_on_entities.py -q` → FAIL

- [ ] **Step 3: 模型加列** 在 `backend/app/models/work_order.py` 的 WorkOrder 类加：

```python
from sqlalchemy import JSON  # 若未导入
# ...
    custom_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
```
（`Any` 从 `typing` 导入、`text` 从 `sqlalchemy` 导入，按文件现状补 import。）

- [ ] **Step 4: schema 加字段** 在 `backend/app/schemas/work_order.py`：
  - `WorkOrderCreate` 加 `custom_values: dict[str, Any] = {}`
  - `WorkOrderUpdate` 加 `custom_values: dict[str, Any] | None = None`
  - `WorkOrderRead` 加 `custom_values: dict[str, Any] = {}`
  - 文件顶部 `from typing import Any`（若无）。

- [ ] **Step 5: service 接线** 在 `backend/app/services/work_order_service.py` 的 create 与 update：
  - create：构造 WorkOrder 前 `custom_field_service.validate_values(db, "work_order", payload.custom_values)`，并把 `custom_values=payload.custom_values` 写入新对象。
  - update：若 `payload.custom_values is not None`：先 `validate_values(db, "work_order", payload.custom_values)`，再 **key 级合并**：`wo.custom_values = {**(wo.custom_values or {}), **payload.custom_values}`。
  - import：`from app.services import custom_field_service`。
  - 若 WorkOrderRead 经 ORM 直接序列化（`response_model`），custom_values 自动带出；确认 update 后 `db.refresh` 或返回对象含新值。

- [ ] **Step 6: 跑测试** `cd backend && .venv/bin/python -m pytest tests/integration/test_custom_values_on_entities.py -k work_order -q` → PASS

- [ ] **Step 7: 门禁 + 提交**

```bash
cd backend && .venv/bin/ruff check app tests && .venv/bin/ruff format app tests && .venv/bin/mypy app && .venv/bin/python -c "import app.main"
git add backend/app/models/work_order.py backend/app/schemas/work_order.py backend/app/services/work_order_service.py backend/tests/integration/test_custom_values_on_entities.py
git commit -m "feat(cf): 工单接入 custom_values（校验+key级合并+读回）"
```

### Task 6-9：asset / request / location / part 接入

对每个实体重复 Task 5 的结构，差异仅在文件路径、entity_type 字面量、Read 序列化方式：

- [ ] **Task 6 — asset**：模型 `app/models/maintenance_asset.py`、schema `app/schemas/asset.py`(`AssetCreate`/`AssetRead`，注意有无独立 Update——若 `AssetUpdate` 派生则同步)、service `app/services/maintenance_asset_service.py`。Asset 走 `to_read` dict 序列化——在 `to_read` 里加 `"custom_values": asset.custom_values or {}`；entity_type=`"asset"`。测试函数 `test_asset_custom_values_roundtrip`（仿 Task5，POST `/api/v1/assets`，建字段 entity_type=asset，body 必填项 `name`）。提交信息 `feat(cf): 资产接入 custom_values`。
- [ ] **Task 7 — request**：模型 `app/models/request.py`、schema `app/schemas/request.py`(`RequestCreate`/`RequestRead`)、service `app/services/request_service.py`。entity_type=`"request"`。请求创建 body 必填 `title`。测试 `test_request_custom_values_roundtrip`。提交 `feat(cf): 请求接入 custom_values`。
- [ ] **Task 8 — location**：模型 `app/models/location.py`、schema `app/schemas/location.py`、service `app/services/location_service.py`（走 `to_read`，加 custom_values）。entity_type=`"location"`。location 必填 `name`。测试 `test_location_custom_values_roundtrip`。提交 `feat(cf): 位置接入 custom_values`。
- [ ] **Task 9 — part**：模型 `app/models/part.py`、schema `app/schemas/part.py`、service `app/services/part_service.py`（part Read 经 `_read_part`/`to_read`——加 custom_values）。entity_type=`"part"`。part 必填 `name`。测试 `test_part_custom_values_roundtrip`。提交 `feat(cf): 备件接入 custom_values`。

每个 Task 的步骤同 Task 5 六步（写测试→失败→模型列→schema→service→测试过→门禁提交）。**每个实体的 service create/update 必须：写前校验 + update key 级合并 + Read 暴露 custom_values。**

- [ ] **Task 10 — Phase 3 收口回归**：`cd backend && .venv/bin/python -m pytest tests/integration/test_custom_values_on_entities.py -q` 全绿；`pytest tests/ -k "work_order or asset or request or location or part" -q` 不破；门禁全过。提交（若有零散修整）`test(cf): Phase3 五实体 custom_values 回归绿`。

---

## Phase 4：前端定义管理页

### Task 11：api 客户端 + 类型

**Files:** Create `frontend/src/api/customFields.ts`, `frontend/src/types/customField.ts`

- [ ] **Step 1: 类型** `frontend/src/types/customField.ts`

```ts
export type CustomFieldType =
  | 'text' | 'number' | 'date' | 'select' | 'multi_select' | 'checkbox' | 'textarea'
export type CustomFieldEntity = 'work_order' | 'asset' | 'request' | 'location' | 'part'

export interface CustomFieldOption { value: string; label?: string; archived?: boolean }
export interface CustomFieldValidation {
  min_length?: number | null; max_length?: number | null; pattern?: string | null
  minimum?: number | null; maximum?: number | null
}
export interface CustomFieldDef {
  id: string; entity_type: CustomFieldEntity; key: string; name: string
  field_type: CustomFieldType; description: string; required: boolean
  default_value: unknown | null; options: CustomFieldOption[]; sort_order: number; status: string
}
export interface CustomFieldCreate {
  entity_type: CustomFieldEntity; key: string; name: string; field_type: CustomFieldType
  description?: string; required?: boolean; default_value?: unknown | null
  options?: CustomFieldOption[]; validation?: CustomFieldValidation; sort_order?: number
}
export type CustomFieldUpdate = Omit<CustomFieldCreate, 'entity_type' | 'key' | 'field_type'>
```

- [ ] **Step 2: api** `frontend/src/api/customFields.ts`

```ts
import { http } from './http'
import type { CustomFieldDef, CustomFieldCreate, CustomFieldUpdate, CustomFieldEntity } from '@/types/customField'

export const listCustomFields = (entityType: CustomFieldEntity, includeArchived = false) =>
  http.get<CustomFieldDef[]>('/custom-fields', { params: { entity_type: entityType, include_archived: includeArchived } }).then((r) => r.data)
export const createCustomField = (p: CustomFieldCreate) =>
  http.post<CustomFieldDef>('/custom-fields', p).then((r) => r.data)
export const updateCustomField = (id: string, p: CustomFieldUpdate) =>
  http.patch<CustomFieldDef>(`/custom-fields/${id}`, p).then((r) => r.data)
export const archiveCustomField = (id: string) =>
  http.patch<CustomFieldDef>(`/custom-fields/${id}/archive`).then((r) => r.data)
export const restoreCustomField = (id: string) =>
  http.patch<CustomFieldDef>(`/custom-fields/${id}/restore`).then((r) => r.data)
export const deleteCustomField = (id: string) =>
  http.delete(`/custom-fields/${id}`).then(() => undefined)
export const reorderCustomFields = (entityType: CustomFieldEntity, orderedIds: string[]) =>
  http.post<CustomFieldDef[]>('/custom-fields/reorder', orderedIds, { params: { entity_type: entityType } }).then((r) => r.data)
```

- [ ] **Step 3: typecheck + 提交**

Run: `cd frontend && npx vue-tsc --noEmit && npx eslint src/api/customFields.ts src/types/customField.ts`
```bash
git add frontend/src/api/customFields.ts frontend/src/types/customField.ts
git commit -m "feat(cf): 前端 customFields api + 类型"
```

### Task 12：定义管理页 `CustomFieldsView.vue` + 路由 + 侧栏

**Files:** Create `frontend/src/views/settings/CustomFieldsView.vue`, `frontend/tests/unit/CustomFieldsView.spec.ts`; Modify `frontend/src/router/routes.ts`, `frontend/src/components/AppSidebar.vue`

- [ ] **Step 1: 写组件**（参考 `src/views/settings/WorkOrderFieldsView.vue` 的结构与权限门控 `auth.hasPermission('company.settings')`）

要点：顶部 `el-select` 切 entity_type（5 选项中文名：工单/资产/请求/位置/备件）；`el-table` 列 name/key/field_type/required/status + 操作（编辑/归档|恢复/删除）；「新建」按钮开 `el-dialog` 表单（entity_type=当前、key(新建可填编辑只读)、name、field_type、required、select 类显示选项编辑器、description、sort_order）；切 entity_type 或增删改后重新 `listCustomFields`。`company.settings` 门控所有写按钮。文案直接中文字面量。

- [ ] **Step 2: 路由** 在 `frontend/src/router/routes.ts` 仿 `/admin/work-order-fields` 加：

```ts
{
  path: '/admin/custom-fields',
  name: 'custom-fields',
  component: () => import('@/views/settings/CustomFieldsView.vue'),
  meta: { title: '自定义字段', requiresAuth: true },
},
```

- [ ] **Step 3: 侧栏入口** 在 `frontend/src/components/AppSidebar.vue` 的「管理/系统配置」组加一项指向 `custom-fields`（仿既有 work-order-fields/request-fields 入口）。

- [ ] **Step 4: 写测试** `frontend/tests/unit/CustomFieldsView.spec.ts`：mount + mock `@/api/customFields`，断言：切实体调 listCustomFields(entity)、渲染返回的字段行、点新建填表提交调 createCustomField。授予 `company.settings` 权限（仿既有 spec 的 auth store 注入）。

- [ ] **Step 5: gate + 提交**

Run: `cd frontend && npx vue-tsc --noEmit && npx eslint <改动文件> && npx vitest run tests/unit/CustomFieldsView.spec.ts`
```bash
git add frontend/src/views/settings/CustomFieldsView.vue frontend/src/router/routes.ts frontend/src/components/AppSidebar.vue frontend/tests/unit/CustomFieldsView.spec.ts
git commit -m "feat(cf): 自定义字段定义管理页 + 路由 + 侧栏入口"
```

---

## Phase 5：CustomFieldsSection 组件 + 5 实体表单/详情接入

### Task 13：可复用 `CustomFieldsSection.vue`

**Files:** Create `frontend/src/components/CustomFieldsSection.vue`, `frontend/tests/unit/CustomFieldsSection.spec.ts`

- [ ] **Step 1: 写组件**

props：`entityType: CustomFieldEntity`、`modelValue: Record<string, unknown>`（即宿主 custom_values）、`readonly?: boolean`。emit `update:modelValue`。
逻辑：onMounted/entityType 变化时 `listCustomFields(entityType)` 取 active 定义；按 `field_type` 渲染：text→`el-input`、textarea→`el-input type=textarea`、number→`el-input-number`、date→`el-date-picker`(value-format `YYYY-MM-DD`)、select→`el-select`、multi_select/checkbox→`el-select multiple` 或 `el-checkbox-group`。每个控件双向绑 `modelValue[key]`（改时 emit 合并后的新对象）。`required` 字段加红星标与本地必填校验展示。`readonly` 时只读展示值。无定义/加载失败时渲染空（不报错）。文案中文。

- [ ] **Step 2: 写测试** `frontend/tests/unit/CustomFieldsSection.spec.ts`：mock `listCustomFields` 返回一个 text + 一个 select 定义；断言渲染对应控件；修改输入 emit `update:modelValue` 含新值；`readonly` 模式不渲染输入控件。

- [ ] **Step 3: gate + 提交**

```bash
cd frontend && npx vue-tsc --noEmit && npx eslint src/components/CustomFieldsSection.vue tests/unit/CustomFieldsSection.spec.ts && npx vitest run tests/unit/CustomFieldsSection.spec.ts
git add frontend/src/components/CustomFieldsSection.vue frontend/tests/unit/CustomFieldsSection.spec.ts
git commit -m "feat(cf): 可复用 CustomFieldsSection 录入/只读组件"
```

### Task 14-18：5 实体表单 + 详情接入

每个实体：① 在创建/编辑表单组件里，表单 state 加 `custom_values: {}`（编辑时回填实体的 `custom_values`），在表单底部加 `<CustomFieldsSection :entity-type="'<entity>'" v-model="form.custom_values" />`，提交 payload 带上 `custom_values`；② 在详情视图加只读展示 `<CustomFieldsSection :entity-type="'<entity>'" :model-value="entity.custom_values" readonly />`。每个 Task 末尾跑该实体既有 spec 确认不破 + 提交。

- [ ] **Task 14 — work_order**：表单 `frontend/src/components/workorder/WorkOrderFormDialog.vue`；详情 `frontend/src/views/maintenance/WorkOrderDetailView.vue`（概览 tab 或新「自定义字段」区）。entity 字面量 `work_order`。
- [ ] **Task 15 — asset**：表单+详情 `frontend/src/views/maindata/AssetsView.vue` 表单 与 `AssetDetailView.vue` 详情。entity `asset`。
- [ ] **Task 16 — request**：`frontend/src/views/maintenance/RequestsView.vue`（创建/编辑对话框 + 详情/抽屉若有）。entity `request`。
- [ ] **Task 17 — location**：`frontend/src/views/maindata/LocationsView.vue` 表单 + `LocationDetailView.vue` 详情。entity `location`。
- [ ] **Task 18 — part**：`frontend/src/views/inventory/PartsView.vue` 表单 + `PartDetailView.vue` 详情。entity `part`。

每个 Task：改完跑 `cd frontend && npx vue-tsc --noEmit && npx eslint <改动> && npx vitest run <该实体既有 spec>`（不破），提交 `feat(cf): <实体> 表单/详情接入自定义字段`。

### Task 19：全量收口

- [ ] **Step 1: 后端全量** `cd backend && .venv/bin/python -m pytest -q`（全绿）+ `.venv/bin/alembic heads`（单 head `custom_field`）+ ruff/format/mypy 净。
- [ ] **Step 2: 前端全量** `cd frontend && npx vue-tsc --noEmit && npx eslint . && npx vitest run`（全绿）。
- [ ] **Step 3: 提交（若有收口修整）** `chore(cf): 全量门禁收口绿`。

---

## 自审备注（实现者注意）

- **共享 compile/merge_options 复用**：Task 4 用到 `field_service.compile_form_to_schema` 与 `_merge_options`。优先把 `_merge_options` 在 Task 1 提为公开 `merge_options`（顺带改 field_service 内部引用），并让 `CustomFieldValidation` 直接 `= FieldValidation`（schema 复用），消除 `# type: ignore`。
- **未知 key 拒绝**仅在 `custom_field_service.validate_values`（业务侧），不在共享模块——共享模块对未知 key 容忍以保 SOP 行为。
- **update key 级合并**是关键正确性点（保留归档字段值），5 实体必须一致。
- **Read 序列化差异**：work_order/request 直接 ORM `response_model`，asset/location/part 走 `to_read` dict——按各自方式暴露 custom_values，勿遗漏 to_read 的实体。
- **迁移 SoftDeleteMixin 列**：建表须显式含 `is_active`/`deleted_at`，以既有带该 mixin 的建表迁移为准。
