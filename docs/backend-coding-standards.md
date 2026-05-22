# 后端代码规范（Backend Coding Standards）

> 适用于 `backend/` 下所有 Python 代码。

## 1. 语言与工具链

| 项 | 选型 / 版本 |
|---|------------|
| Python | 3.11+ |
| 包管理 | `pip` + `requirements.txt`（开发期可选 `uv`） |
| 格式化 | `ruff format`（替代 black） |
| Linter | `ruff` |
| 类型检查 | `mypy --strict`（service / model 层）/ `--no-strict-optional`（router 层） |
| 测试 | `pytest` + `pytest-cov` + `httpx`（API 测试） |
| 钩子 | `pre-commit`（强制 ruff + mypy） |

### 1.1 工具配置（关键约定）

`pyproject.toml` 中固化以下规则：

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "SIM", "RUF"]
ignore = ["E501"]  # 由 formatter 处理
```

## 2. 目录与分层

后端严格分四层，**禁止跨层调用**：

```
routers/    # HTTP 路由层：参数校验、调度 service、不写业务逻辑
schemas/    # Pydantic 模型：请求 / 响应 DTO
services/   # 业务逻辑层：组织 model 完成业务，可被多个 router 复用
models/     # ORM 层：SQLAlchemy 模型 + 表关系
```

**调用方向**：`router → service → model`，**绝对不能**反向调用。`schemas` 可以被 router 和 service 引用，但不能依赖 `models`（避免循环）。

### 2.1 模块命名

| 类型 | 命名 | 例 |
|------|------|----|
| 模块文件 | 小写蛇形 | `procedure_service.py` |
| 类 | 大驼峰 | `class ProcedureService` |
| 函数 / 变量 | 小写蛇形 | `def create_procedure(...)` |
| 常量 | 全大写蛇形 | `MAX_FOLDER_DEPTH = 5` |
| 私有 | 前缀单下划线 | `_calculate_depth` |

## 3. 类型注解

**强制要求**：所有公共函数 / 方法必须有完整的参数与返回值类型注解。

```python
# 推荐
def create_procedure(db: Session, payload: ProcedureCreate) -> Procedure:
    ...

# 禁止
def create_procedure(db, payload):
    ...
```

- ORM 模型用 SQLAlchemy 2.0 的 `Mapped[T]`、`mapped_column()`
- Pydantic 模型必须显式声明类型，禁止裸 `Any`（必要时用 `dict[str, Any]` 并加注释）
- 复杂联合类型用 `TypeAlias` 提取

## 4. FastAPI 路由

### 4.1 路由文件结构

```python
# routers/folders.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_db, get_request_meta
from app.schemas.folder import FolderCreate, FolderRead, FolderUpdate
from app.services import folder_service

router = APIRouter(prefix="/folders", tags=["folders"])


@router.post("", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: FolderCreate,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Folder:
    return folder_service.create(db, payload, meta)
```

**强制**：

- router 函数体不超过 15 行，**仅做参数转发**；业务逻辑全在 service
- `response_model` 必须显式指定
- 状态码使用 `status.HTTP_*` 常量，禁止裸数字
- 用 Depends 注入 db / meta，禁止 `Request` 直接出现在 router 签名（除特殊场景）

### 4.2 错误处理

- 业务异常：抛 `HTTPException`，状态码语义化（400 参数、404 找不到、409 冲突、422 校验）
- 系统异常：让全局异常处理器接管，**不要 catch 后 re-raise**
- 异常 detail 用结构化对象：
  ```python
  raise HTTPException(
      status_code=409,
      detail={"code": "FOLDER_NAME_DUPLICATE", "message": "同一父目录下已存在该名称"},
  )
  ```

详见 [api-specification.md](api-specification.md) 的错误码表。

## 5. SQLAlchemy 与数据库

### 5.1 模型定义

```python
# models/folder.py
from datetime import datetime
from uuid import UUID

from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class Folder(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tb_folder"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(20), default="")
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("tb_folder.id"))
    system: Mapped[bool] = mapped_column(Boolean, default=False)
    full_path: Mapped[str] = mapped_column(default="")

    parent: Mapped["Folder | None"] = relationship(remote_side="Folder.id", back_populates="children")
    children: Mapped[list["Folder"]] = relationship(back_populates="parent")
```

**规范**：

- 表名加 `tb_` 前缀 + 单数蛇形（B6 决策）：`tb_folder`、`tb_procedure_chapter`
- 字段顺序：`id` → 业务字段 → `is_active` → 时间戳（继承 mixin）
- 所有外键写明 `ondelete`（默认 RESTRICT）
- 复杂关系用 `back_populates` 而非 `backref`

### 5.2 查询规范

- **禁止**在 router 层直接 query；所有 query 封装到 service
- 多表 join 用 `joinedload()` / `selectinload()` 防 N+1
- 写操作必须显式 `db.commit()`，service 内不调用 `db.rollback()`（由全局异常处理器处理）
- 事务边界：service 函数即一个事务；跨函数事务用 `with db.begin():` 显式管理

### 5.3 软删除

- 所有业务表继承 `SoftDeleteMixin`，提供 `is_active: bool` + `deleted_at: datetime | None`
- 查询默认过滤 `is_active=True`，封装为 `Query` helper：

```python
def alive(query):
    return query.filter(Model.is_active.is_(True))
```

详见 [database-specification.md](database-specification.md)。

## 6. Pydantic Schema

### 6.1 命名约定

每个资源至少 3 个 Pydantic 模型：

```python
class FolderBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    prefix: str = Field("", max_length=20)


class FolderCreate(FolderBase):
    parent_id: UUID | None = None


class FolderUpdate(BaseModel):  # 注意：Update 用全部 Optional
    name: str | None = None
    prefix: str | None = None
    parent_id: UUID | None = None


class FolderRead(FolderBase):
    id: UUID
    full_path: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 6.2 校验

- 用 Pydantic 内置 `Field()` 表达约束，复杂校验用 `field_validator` / `model_validator`
- 字符串字段统一加 `min_length` / `max_length`
- 时间字段用 `datetime`（带时区，UTC）

## 7. 错误处理与日志

### 7.1 日志

- 用标准库 `logging`，禁止 `print()`
- 每个模块文件开头：`logger = logging.getLogger(__name__)`
- 关键操作必须有 INFO 级日志（创建 / 删除 / 状态变更）
- 异常必须 `logger.exception()` 含 traceback
- **禁止**在日志中输出敏感信息（请求体若含敏感字段需脱敏）

### 7.2 日志格式（Q329）

- **生产 = 结构化 JSON**（字段 `time/level/logger/message/request_id`），便于容器平台采集；**开发 = 人读文本**。按 `APP_ENV` 切 formatter，由 `app/config.py` 统一配置。
- **request-id 中间件**：读 `X-Request-Id`，缺失则生成 uuid，注入日志上下文 + 回写响应头。
- 不上 APM / 应用内指标后端 / 分布式链路追踪（Q329）；业务可观测性由审计日志覆盖。

```
# dev（人读）
2026-05-18 10:23:45 [INFO] app.services.procedure_service: procedure created code=QC-0001 id=... request_id=...
# prod（JSON）
{"time":"2026-05-18T10:23:45Z","level":"INFO","logger":"app.services.procedure_service","message":"procedure created code=QC-0001 id=...","request_id":"..."}
```

## 8. 测试

详见 [testing-standards.md](testing-standards.md)。本节只列后端特有要求：

- 单元测试目录：`backend/tests/unit/`（按模块对应）
- 集成测试：`backend/tests/integration/`（用 `TestClient` 调 API）
- 测试用 SQLite in-memory 数据库（CI）；本地可用 MySQL test schema
- Fixture 写在 `conftest.py`，禁止跨 conftest 隐式依赖

## 9. 依赖管理

- 新增第三方库必须在 PR 说明用途
- 区分 `requirements.txt`（运行时）与 `requirements-dev.txt`（开发 + 测试）
- 锁定主版本号：`fastapi>=0.115,<0.116`

## 10. 安全

- **禁止**字符串拼接 SQL，全部走 ORM 或 `text()` + 参数绑定
- 文件上传必须校验扩展名 + MIME + 大小上限（≤ 50MB）
- 密钥（如有）从环境变量读取，**禁止**硬编码
- 上线前用 `bandit` 扫一遍
