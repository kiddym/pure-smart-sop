# Phase 5B 邮件通知 + 生产级文件存储 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 5A 站内通知同步投递为邮件（outbox + 调度异步投递 + 可插拔 EmailBackend + per-user 偏好），并把持久产物（asset/attachment/source_docx）的物理 IO 收口到可插拔 StorageBackend（Local/S3），使存储后端可切换且对数据层透明。

**Architecture:** 两个相互独立的后端子系统，合并一期。邮件：事件发生时在 5A `notify()` 单一入口内部按偏好写 `email_outbox` 行（同事务原子），独立调度 tick 扫 `pending` 行经 `EmailBackend` 投递并写回状态/重试。存储：抽 `StorageBackend` 协议（write/read/delete/exists），LocalBackend 等价现状、S3Backend 用 boto3；三类持久产物 service 的 per-file blob IO 收口到后端，DB 仍存相对 `storage_path`（= backend key），零迁移；source_docx 的目录枚举型孤儿清理保持本地 FS（仅 local 后端有效）。

**Tech Stack:** FastAPI · SQLAlchemy 2.0(sync) · Pydantic v2 · SQLite(test)/MySQL(prod) · Alembic · APScheduler · stdlib smtplib · boto3(新增依赖) · pytest

---

## 全局约定（每个任务都适用）

- **激活环境**：任何 python/pytest 前先 `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate`。
- **清缓存**（偶发 import 陈旧时）：`find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache`，跑测试带 `PYTHONDONTWRITEBYTECODE=1`。
- **共享 worktree 防串扰**：每次 `git commit` 前先 `git diff --cached --name-only` 确认只含本 task 文件；只精确 `git add <具体文件>`，禁 `git add .` / `git add -A`。收尾时若 `git status` 仍有非本期游离改动（如 `docs/word-parser-solution.md`、`content-row-type-tag` 等其他会话遗留），不要提交、不要 revert。
- **既有共享文件**（`config.py` / `scheduler.py` / `models/__init__.py` / `notification_service.py` / `asset_service.py` / `attachment_service.py` / `source_docx_service.py`）一律用精确 Edit 替换，绝不 sed/正则批改。
- **提交 trailer 最后一行**：`Co-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>`（是 "4.5" 不是 4.8）。
- **clean-room**：不出现 "Atlas" 字样、不抄任何第三方源码/DDL/文案。
- **基线**：开工前确认 `pytest -q` 全绿（5A 后基线 1077 passed）、`alembic heads` 单 head = `phase5a_notification`、`git branch --show-current` = `phase-0-platform-foundation`。**不创建分支、不合并。**
- **任务顺序为依赖序**，请按序执行。每个 commit 一个 task。

---

## Task 1: 配置项（email_* / storage_* / s3_*）

**Files:**
- Modify: `app/config.py`（在 `notify_due_soon_days` 行所在区块之后追加）
- Test: `tests/unit/test_config_phase5b.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_config_phase5b.py
"""Phase 5B 配置项默认值（开箱即用、测试零网络）。"""
from __future__ import annotations

from app.config import settings


def test_email_defaults():
    assert settings.email_backend == "console"
    assert settings.email_from == "no-reply@smart-cmms.local"
    assert settings.email_max_attempts == 5
    assert settings.smtp_port == 587
    assert settings.smtp_use_tls is True


def test_storage_defaults():
    assert settings.storage_backend == "local"
    assert settings.s3_bucket == ""
    assert settings.s3_endpoint_url == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && pytest tests/unit/test_config_phase5b.py -q`
Expected: FAIL（`AttributeError: 'Settings' object has no attribute 'email_backend'`）

- [ ] **Step 3: 实现 — 在 `app/config.py` 的 `notify_due_soon_days` 行下方、`asset_gc_grace_hours` 行上方插入。** 用 Edit 精确替换：

old_string:
```python
    notify_due_soon_days: int = 3  # 工单到期提醒提前天数（Phase 5A）
    asset_gc_grace_hours: int = 24  # asset ref_count=0 宽限（Q333）
```
new_string:
```python
    notify_due_soon_days: int = 3  # 工单到期提醒提前天数（Phase 5A）
    asset_gc_grace_hours: int = 24  # asset ref_count=0 宽限（Q333）

    # 邮件通知（Phase 5B）
    email_backend: str = "console"  # console | smtp | memory(测试)
    email_from: str = "no-reply@smart-cmms.local"
    email_max_attempts: int = 5  # outbox 投递重试上限
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # 文件存储后端（Phase 5B）
    storage_backend: str = "local"  # local | s3
    s3_bucket: str = ""
    s3_endpoint_url: str = ""  # 空=AWS 默认 endpoint；填写以兼容 MinIO 等
    s3_region: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_config_phase5b.py -q`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add app/config.py tests/unit/test_config_phase5b.py
git commit -m "$(printf 'feat(phase-5b): add email + storage backend settings\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 2: StorageBackend 协议 + LocalBackend + 工厂

**Files:**
- Create: `app/storage_backends/__init__.py`、`app/storage_backends/base.py`、`app/storage_backends/local.py`
- Test: `tests/unit/test_storage_backend_local.py`（新建）

设计：`key` = 现有 DB 里存的相对 `storage_path`（如 `asset/ab/abcd.png`）。`get_storage_backend()` 按 `settings.storage_backend` 返回单例；测试默认 `local`，物理根由 `settings.storage_dir` 决定（沿用既有 `storage_tmp` fixture）。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_storage_backend_local.py
"""LocalBackend：等价现有磁盘行为，key=相对路径。"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.storage_backends import get_storage_backend
from app.storage_backends.local import LocalBackend


def test_write_read_roundtrip(storage_tmp: Path):
    b = LocalBackend()
    b.write("asset/ab/x.bin", b"hello")
    assert b.read("asset/ab/x.bin") == b"hello"
    assert (storage_tmp / "asset/ab/x.bin").read_bytes() == b"hello"


def test_exists(storage_tmp: Path):
    b = LocalBackend()
    assert b.exists("a/b.txt") is False
    b.write("a/b.txt", b"1")
    assert b.exists("a/b.txt") is True


def test_read_missing_raises(storage_tmp: Path):
    with pytest.raises(FileNotFoundError):
        LocalBackend().read("nope/x")


def test_delete_idempotent(storage_tmp: Path):
    b = LocalBackend()
    b.write("d/x", b"1")
    b.delete("d/x")
    assert b.exists("d/x") is False
    b.delete("d/x")  # 再删不报错


def test_factory_returns_local_by_default(storage_tmp: Path):
    assert isinstance(get_storage_backend(), LocalBackend)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_storage_backend_local.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.storage_backends'`）

- [ ] **Step 3: 实现**

```python
# app/storage_backends/base.py
"""存储后端协议（Phase 5B）。key 为相对路径字符串（= DB 里存的相对 storage_path）。"""
from __future__ import annotations

from typing import Protocol


class StorageBackend(Protocol):
    """最小持久对象存储接口。read 不存在抛 FileNotFoundError；delete 幂等。"""

    def write(self, key: str, data: bytes) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
```

```python
# app/storage_backends/local.py
"""本地磁盘后端：等价 Phase 0–4 现有落盘行为。"""
from __future__ import annotations

from pathlib import Path

from app import storage


class LocalBackend:
    def _path(self, key: str) -> Path:
        return storage.storage_root() / key

    def write(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()  # 不存在自然抛 FileNotFoundError

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()
```

```python
# app/storage_backends/__init__.py
"""存储后端工厂（Phase 5B）。按 settings.storage_backend 返回单例。

测试可 monkeypatch settings.storage_backend，并调用 reset_storage_backend() 清缓存；
local 后端的物理根由 settings.storage_dir 决定（沿用 storage_tmp fixture）。
"""
from __future__ import annotations

from app.config import settings
from app.storage_backends.base import StorageBackend

_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    global _backend
    if _backend is None:
        _backend = _build()
    return _backend


def reset_storage_backend() -> None:
    """测试钩子：丢弃缓存单例，下次按当前 settings 重建。"""
    global _backend
    _backend = None


def _build() -> StorageBackend:
    if settings.storage_backend == "s3":
        from app.storage_backends.s3 import S3Backend
        return S3Backend()
    from app.storage_backends.local import LocalBackend
    return LocalBackend()
```

> 注：`get_storage_backend()` 缓存单例。Local 后端无状态、根目录运行时从 `settings.storage_dir` 读，故 `storage_tmp` fixture monkeypatch `storage_dir` 后无需 reset。`reset_storage_backend()` 供切换 backend 的测试（Task 3）用。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_storage_backend_local.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add app/storage_backends/ tests/unit/test_storage_backend_local.py
git commit -m "$(printf 'feat(phase-5b): StorageBackend protocol + LocalBackend + factory\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 3: S3Backend（boto3，注入式 client）

**Files:**
- Modify: `pyproject.toml`（加 boto3 依赖）
- Create: `app/storage_backends/s3.py`
- Test: `tests/unit/test_storage_backend_s3.py`（新建，用手写 fake client，不连真 S3）

设计：`S3Backend(client=None, bucket=None)` 允许注入 client 以便测试；缺省从 boto3 + settings 构造。`get_object` 命中 `ClientError`(404/NoSuchKey) → 抛 `FileNotFoundError` 对齐 Local。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_storage_backend_s3.py
"""S3Backend：用手写 fake boto3 client 验证 key 映射与语义，不连真 S3。"""
from __future__ import annotations

import pytest
from botocore.exceptions import ClientError

from app.storage_backends.s3 import S3Backend


class _FakeS3:
    """最小内存 fake：put/get/delete/head_object。"""

    def __init__(self):
        self.store: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket, Key, Body):
        self.store[(Bucket, Key)] = Body

    def get_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.store:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": _Body(self.store[(Bucket, Key)])}

    def delete_object(self, *, Bucket, Key):
        self.store.pop((Bucket, Key), None)

    def head_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.store:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}


class _Body:
    def __init__(self, data): self._data = data
    def read(self): return self._data


def _backend():
    return S3Backend(client=_FakeS3(), bucket="b")


def test_write_read_roundtrip():
    b = _backend()
    b.write("asset/ab/x.bin", b"hello")
    assert b.read("asset/ab/x.bin") == b"hello"


def test_read_missing_raises_filenotfound():
    with pytest.raises(FileNotFoundError):
        _backend().read("missing/x")


def test_exists():
    b = _backend()
    assert b.exists("a/x") is False
    b.write("a/x", b"1")
    assert b.exists("a/x") is True


def test_delete_idempotent():
    b = _backend()
    b.write("d/x", b"1")
    b.delete("d/x")
    assert b.exists("d/x") is False
    b.delete("d/x")  # 不报错
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_storage_backend_s3.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.storage_backends.s3'` 或 boto3 未装）

- [ ] **Step 3a: 加 boto3 依赖** — 在 `pyproject.toml` 的依赖列表里追加 `boto3`（用 Edit 在 dependencies 数组中加一行 `"boto3>=1.34",`，紧邻其他运行依赖），然后安装：

Run: `pip install "boto3>=1.34"`
Expected: 成功安装 boto3 + botocore。

- [ ] **Step 3b: 实现 `app/storage_backends/s3.py`**

```python
# app/storage_backends/s3.py
"""S3 / S3-兼容（MinIO 等）对象存储后端（Phase 5B）。

key 即 bucket 内 object key（= DB 相对 storage_path）。client 可注入以便测试。
"""
from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from app.config import settings

_NOT_FOUND_CODES = {"NoSuchKey", "404", "NoSuchBucket"}


class S3Backend:
    def __init__(self, client: Any | None = None, bucket: str | None = None) -> None:
        self._bucket = bucket if bucket is not None else settings.s3_bucket
        self._client = client if client is not None else self._make_client()

    def _make_client(self) -> Any:  # pragma: no cover — 真实 client，不在单测覆盖
        import boto3
        kwargs: dict[str, Any] = {}
        if settings.s3_endpoint_url:
            kwargs["endpoint_url"] = settings.s3_endpoint_url
        if settings.s3_region:
            kwargs["region_name"] = settings.s3_region
        if settings.s3_access_key:
            kwargs["aws_access_key_id"] = settings.s3_access_key
            kwargs["aws_secret_access_key"] = settings.s3_secret_key
        return boto3.client("s3", **kwargs)

    def write(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def read(self, key: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                raise FileNotFoundError(key) from e
            raise
        return resp["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)  # S3 delete 本身幂等

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES:
                return False
            raise
        return True
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_storage_backend_s3.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml app/storage_backends/s3.py tests/unit/test_storage_backend_s3.py
git commit -m "$(printf 'feat(phase-5b): S3Backend (boto3, injectable client)\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 4: asset_service 物理 IO 收口到 StorageBackend

**Files:**
- Modify: `app/services/asset_service.py`（行 ~83-86 写、~217-220 读、~251-253 删）
- Modify: `app/tasks/asset_gc.py`（物理删走 backend）
- Test: 既有 `tests/unit/test_tasks.py`（asset_gc 回归）、`tests/unit/...` asset 相关 + 新增 `tests/unit/test_asset_storage_backend.py`

> 现状（精确锚点，实现前先 Read 这些函数确认行号未漂移）：
> - `find_or_create_asset`：`path = storage.asset_path(sha, norm_ext)`；若新建 `path.write_bytes(data)`；`rel = path.relative_to(storage.storage_root()).as_posix()`。
> - 读（`load`/约行 217）：`path = storage.storage_root() / asset.storage_path; if not path.exists(): ...; return path.read_bytes(), asset.mime_type`。
> - `delete_asset_locked`（约行 251）：`path = storage.storage_root() / asset.storage_path; ...; path.unlink()`。

- [ ] **Step 1: 写失败测试 — 验证收口后写经 backend、且去重 exists 检查走 backend**

```python
# tests/unit/test_asset_storage_backend.py
"""asset_service 物理 IO 经 StorageBackend（Phase 5B 收口）。"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.services import asset_service
from app.storage_backends import get_storage_backend
from tests.unit.parser._docx_builder import tiny_png


def test_find_or_create_writes_via_backend(db: Session, storage_tmp: Path):
    asset = asset_service.find_or_create_asset(db, tiny_png(), ext=".png")
    # 收口后：物理字节可经 backend.read(相对 key) 取回
    assert get_storage_backend().read(asset.storage_path) == tiny_png()


def test_load_reads_via_backend(db: Session, storage_tmp: Path):
    asset = asset_service.find_or_create_asset(db, tiny_png(), ext=".png")
    data, mime = asset_service.load(db, asset.id)  # 若现有读函数名不同，按实际调整
    assert data == tiny_png()
```

> 实现者注：Step 1 测试里的读函数名 `asset_service.load` 是占位——执行前 Read `asset_service.py` 确认实际读取入口（约行 217 的函数）名字与签名，改成真实名。若读路径只在 router 暴露，则改测 router 或直接断言 `get_storage_backend().exists(asset.storage_path) is True`。

- [ ] **Step 2: 跑测试确认失败（或现有 asset 测试仍绿）**

Run: `pytest tests/unit/test_asset_storage_backend.py -q`
Expected: 新断言可能已巧合通过（因 LocalBackend 落同一磁盘根）——这正是收口"零行为变化"的体现。**关键判据改为：grep 确认 `asset_service.py` 不再直接 `write_bytes/read_bytes/unlink`。**

- [ ] **Step 3: 实现 — 用 Edit 精确替换三处**

写（find_or_create）：
old_string:
```python
    path = storage.asset_path(sha, norm_ext)
```
（连同其后的 `path.write_bytes(data)` 与 `rel = ...` 整块）替换为先算相对 key、`exists` 去重判断、`write`：
new_string（按实际上下文调整变量名）：
```python
    path = storage.asset_path(sha, norm_ext)
    rel = path.relative_to(storage.storage_root()).as_posix()
    from app.storage_backends import get_storage_backend
    backend = get_storage_backend()
    if not backend.exists(rel):
        backend.write(rel, data)
```
（删除原 `path.write_bytes(data)`；`rel` 若原本在写之后计算，调整为写之前。）

读（约行 217）：
old_string:
```python
    path = storage.storage_root() / asset.storage_path
    if not path.exists():
        ...
    return path.read_bytes(), asset.mime_type
```
new_string（保留原 404/异常分支语义，仅换 IO）：
```python
    from app.storage_backends import get_storage_backend
    try:
        data = get_storage_backend().read(asset.storage_path)
    except FileNotFoundError:
        ...  # 保留原"文件缺失"分支处理
    return data, asset.mime_type
```

删（delete_asset_locked，约行 251）：
old_string:
```python
    path = storage.storage_root() / asset.storage_path
    ...
    path.unlink()
```
new_string:
```python
    from app.storage_backends import get_storage_backend
    get_storage_backend().delete(asset.storage_path)
```

`app/tasks/asset_gc.py`：若其物理删调用 `asset_service.delete_asset_locked`，则自动随上面收口；若它自行 `unlink`，同样换 `get_storage_backend().delete(key)`。先 Read 确认。

> 把 `from app.storage_backends import get_storage_backend` 提到文件顶部 import 区（与其他 import 一起，按字母序），避免函数内重复 import；上面函数内 import 仅为示意最小 diff，实现时统一放顶部并跑 ruff。

- [ ] **Step 4: 跑测试 — 新测 + 既有 asset/asset_gc 回归全绿**

Run: `pytest tests/unit/test_asset_storage_backend.py tests/unit/test_tasks.py -q && grep -nE "write_bytes|read_bytes|\.unlink\(" app/services/asset_service.py`
Expected: 测试 PASS；grep 在 asset_service 中**不再有** asset 永久文件的 `write_bytes/read_bytes/unlink`（tmp/media 读保留——那是临时件不收口）。

- [ ] **Step 5: 提交**

```bash
git add app/services/asset_service.py app/tasks/asset_gc.py tests/unit/test_asset_storage_backend.py
git commit -m "$(printf 'refactor(phase-5b): route asset_service blob IO through StorageBackend\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 5: attachment_service 物理 IO 收口

**Files:**
- Modify: `app/services/attachment_service.py`（`_file_or_404`/`upload`/`download`/`preview`/孤儿删 `delete_orphan_path`）
- Test: 既有附件测试回归 + 新增 `tests/unit/test_attachment_storage_backend.py`

> 现状锚点（实现前 Read 确认）：`_file_or_404`（行~83）`path = storage.storage_root() / att.storage_path; if not path.exists(): 404; return path`；`download`（~115）`return _file_or_404(att).read_bytes(), ...`；`preview`（~121）同；`upload`（~161-164）`path = storage.attachment_path(uid, ...); path.write_bytes(data); rel = path.relative_to(...)`；`delete_orphan_path`（~295-304）`abs_path = storage.storage_root() / storage_path; ... unlink`。

- [ ] **Step 1: 写失败/收口验证测试**

```python
# tests/unit/test_attachment_storage_backend.py
"""attachment_service 物理 IO 经 StorageBackend（Phase 5B 收口）。"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.services import attachment_service
from app.storage_backends import get_storage_backend
from tests.conftest import Factory


def test_upload_then_download_via_backend(db: Session, factory: Factory, storage_tmp: Path):
    leaf = factory.folder(name="叶", prefix="QC", full_path="叶")
    factory.sequence(leaf.id)
    proc = factory.procedure(leaf.id)
    meta = RequestMeta(ip_address="1.1.1.1", user_agent="ua", request_id="r")
    att = attachment_service.upload(
        db, proc.id, b"hello", "a.txt", content_type="text/plain", description="", meta=meta)
    assert get_storage_backend().read(att.storage_path) == b"hello"
    data, mime, name = attachment_service.download(db, att.id)
    assert data == b"hello"
```

- [ ] **Step 2: 跑测试**

Run: `pytest tests/unit/test_attachment_storage_backend.py -q`
Expected: 同 Task 4，可能巧合通过；硬判据 = Step 4 的 grep。

- [ ] **Step 3: 实现 — Edit 精确替换**

`upload`：
old_string:
```python
    path = storage.attachment_path(uid, Path(name).suffix)
    ...
    path.write_bytes(data)
    rel = path.relative_to(storage.storage_root()).as_posix()
```
new_string:
```python
    path = storage.attachment_path(uid, Path(name).suffix)
    rel = path.relative_to(storage.storage_root()).as_posix()
    get_storage_backend().write(rel, data)
```

`_file_or_404` + `download`/`preview`：把"返回 Path 再 `.read_bytes()`"改为先 `exists` 判 404、再 `read`。
old_string（`_file_or_404`）:
```python
def _file_or_404(att: ProcedureAttachment) -> Path:
    path = storage.storage_root() / att.storage_path
    if not path.exists():
        ...
    return path
```
new_string（改为返回 bytes 的 helper，或保留并改 download/preview 直接用 backend）：
```python
def _bytes_or_404(att: ProcedureAttachment) -> bytes:
    backend = get_storage_backend()
    if not backend.exists(att.storage_path):
        ...  # 保留原 404 抛错
    return backend.read(att.storage_path)
```
并把 `download`/`preview` 里的 `_file_or_404(att).read_bytes()` 改为 `_bytes_or_404(att)`。

`delete_orphan_path`：
old_string:
```python
    abs_path = storage.storage_root() / storage_path
    ...
    abs_path.unlink(...)
```
new_string:
```python
    get_storage_backend().delete(storage_path)
```

顶部 import 加 `from app.storage_backends import get_storage_backend`（字母序）。

- [ ] **Step 4: 跑测试 + grep 判据**

Run: `pytest tests/unit/test_attachment_storage_backend.py tests/unit/test_tasks.py -q && grep -nE "write_bytes|read_bytes|\.unlink\(" app/services/attachment_service.py`
Expected: PASS；attachment_service 中不再有附件文件 `write_bytes/read_bytes/unlink`。

- [ ] **Step 5: 提交**

```bash
git add app/services/attachment_service.py tests/unit/test_attachment_storage_backend.py
git commit -m "$(printf 'refactor(phase-5b): route attachment_service blob IO through StorageBackend\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 6: source_docx_service 单文件 IO 收口（目录枚举型孤儿清理保持本地）

**Files:**
- Modify: `app/services/source_docx_service.py`（`store_from_token` 写+回滚、`get_for_procedure` 读、`delete_for_group` 删）
- Test: 既有 `tests/unit/test_source_docx_service.py` + `tests/unit/test_tasks.py`（sweep 回归）+ 新增断言

> **重要边界**：`orphan_group_ids`（扫目录树）、`delete_group_dir`（`shutil.rmtree`）、`sweep_source_docx` 任务是**目录枚举型孤儿清理**，不映射到最小 backend 接口（S3 无目录）。**这些保持直接操作本地 FS（`storage.source_docx_root()`），仅在 local 后端下有效；S3 下源 docx 孤儿清理属未来 ops 工具。** 本任务**只收口 per-file 的写/读/删**。这一限制要在代码注释与收尾 status 里写明（no silent caps）。

- [ ] **Step 1: 写收口验证测试**

```python
# 追加到 tests/unit/test_source_docx_service.py（或新建 test_source_docx_storage_backend.py）
from pathlib import Path
from app.storage_backends import get_storage_backend


def test_store_then_get_via_backend(db, storage_tmp: Path):
    from app.services import source_docx_service, upload_service
    from tests.unit.parser._docx_builder import styled_sop
    up = upload_service.save_upload(styled_sop(), "ok.docx")
    row = source_docx_service.store_from_token(
        db, procedure_group_id="pg-1", upload_token=up.upload_token)
    db.commit()
    assert get_storage_backend().exists(row.storage_path) is True
```

> 实现者注：`store_from_token` 返回值/字段名以实际为准，先 Read。`styled_sop`/`save_upload` 沿用既有测试用法（见 `test_tasks.py`）。

- [ ] **Step 2: 跑测试**

Run: `pytest tests/unit/test_source_docx_service.py -q`
Expected: 先红或巧合绿；硬判据见 Step 4。

- [ ] **Step 3: 实现 — Edit 精确替换三处（保留回滚语义）**

`store_from_token`（写，约行 58-62）：
old_string:
```python
    path.parent.mkdir(parents=True, exist_ok=True)
    ...
        path.write_bytes(data)
    ...
        path.unlink(missing_ok=True)  # 清半截文件；行随事务回滚消失
```
new_string（用 backend.write；失败回滚改 backend.delete）：
```python
    rel = str(path.relative_to(storage.storage_root()))
    backend = get_storage_backend()
    try:
        backend.write(rel, data)
    except Exception:
        backend.delete(rel)  # 清半截文件；行随事务回滚消失
        raise
```

`get_for_procedure`（读，约行 81-82）：原返回 `(Path, ...)`。下游若需 Path，则改为返回 bytes，或在 router 层改用 backend。先 Read 看调用方。最小改法：保留函数签名但内部用 `backend.exists` 判存在、读取处改 `backend.read(row.storage_path)`。若调用方强依赖 Path（如直接传给 parser 读文件），则**该读路径维持本地**并在注释标注（S3 下需先 download 到临时文件——属未来工作）。**执行前必须 Read 调用方确认**。

`delete_for_group`（删，约行 113）：
old_string:
```python
    (storage.storage_root() / row.storage_path).unlink(missing_ok=True)
```
new_string:
```python
    get_storage_backend().delete(row.storage_path)
```

`orphan_group_ids` / `delete_group_dir` / `sweep_source_docx`：**不改**，加一行注释说明目录枚举型清理仅 local 后端有效。

顶部 import 加 `from app.storage_backends import get_storage_backend`。

- [ ] **Step 4: 跑测试 + grep**

Run: `pytest tests/unit/test_source_docx_service.py tests/unit/test_tasks.py -q && grep -nE "write_bytes|\.unlink\(missing_ok" app/services/source_docx_service.py`
Expected: PASS；`store_from_token`/`delete_for_group` 的 per-file IO 已收口（`rmtree` 在 `delete_group_dir` 保留属预期）。

- [ ] **Step 5: 提交**

```bash
git add app/services/source_docx_service.py tests/unit/test_source_docx_service.py
git commit -m "$(printf 'refactor(phase-5b): route source_docx per-file IO through StorageBackend\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 7: NotificationPreference + EmailOutbox 模型

**Files:**
- Create: `app/models/notification_preference.py`、`app/models/email_outbox.py`
- Test: `tests/unit/test_email_models.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_email_models.py
"""Phase 5B 邮件模型：偏好 + 投递 outbox。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.email_outbox import EmailOutbox
from app.models.notification_preference import NotificationPreference


def test_preference_defaults(db: Session):
    p = NotificationPreference(company_id="co-1", user_id="u-1")
    db.add(p)
    db.commit()
    db.refresh(p)
    assert p.email_enabled is True
    assert p.disabled_types == "[]"


def test_outbox_defaults(db: Session):
    o = EmailOutbox(company_id="co-1", recipient_user_id="u-1",
                    recipient_email="a@x.com", type="WO_ASSIGNED",
                    subject="s", body="b")
    db.add(o)
    db.commit()
    db.refresh(o)
    assert o.status == "pending"
    assert o.attempts == 0
    assert o.sent_at is None
    rows = db.execute(select(EmailOutbox)).scalars().all()
    assert len(rows) == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_email_models.py -q`
Expected: FAIL（`ModuleNotFoundError: app.models.notification_preference`）

- [ ] **Step 3: 实现**

```python
# app/models/notification_preference.py
"""邮件通知偏好（Phase 5B）：全局总闸 + 被禁类型黑名单。每用户一行。"""
from __future__ import annotations

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class NotificationPreference(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_notification_preference"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", name="uq_notif_pref_user"),
    )

    user_id: Mapped[str] = mapped_column(String(36), index=True)
    email_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1")
    # json 数组：被关掉的通知类型码（黑名单）。空 = 全开。
    disabled_types: Mapped[str] = mapped_column(
        Text, default="[]", server_default="[]")
```

```python
# app/models/email_outbox.py
"""邮件投递队列（Phase 5B）：append-only。tick 扫 pending 投递。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, TenantMixin, TimestampMixin, UUIDMixin


class EmailOutbox(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_email_outbox"
    __table_args__ = (
        Index("ix_email_outbox_status", "company_id", "status"),
    )

    recipient_user_id: Mapped[str] = mapped_column(String(36), index=True)
    recipient_email: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(40))
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    sent_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    notification_id: Mapped[str | None] = mapped_column(String(36), default=None)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_email_models.py -q`
Expected: PASS（2 passed）。若 ruff I001 import 排序报错，跑 `ruff check --fix app/models/notification_preference.py app/models/email_outbox.py`。

- [ ] **Step 5: 提交**

```bash
git add app/models/notification_preference.py app/models/email_outbox.py tests/unit/test_email_models.py
git commit -m "$(printf 'feat(phase-5b): NotificationPreference + EmailOutbox models\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 8: 迁移 phase5b_email_storage + 模型注册

**Files:**
- Create: `alembic/versions/20260531_0016_phase5b_email_storage.py`
- Modify: `app/models/__init__.py`（注册两模型）
- Test: `tests/unit/test_migration_phase5b.py`（新建，前后滚）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_migration_phase5b.py
"""迁移 phase5b_email_storage 建表 + 对称回滚（SQLite 临时库）。"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _alembic(db_url: str, *args: str):
    import os
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(["alembic", *args], cwd="...", env=env,
                          capture_output=True, text=True)


def test_upgrade_creates_then_downgrade_drops(tmp_path: Path):
    db = tmp_path / "p5b.db"
    url = f"sqlite:///{db}"
    import os
    env = {**os.environ, "DATABASE_URL": url}
    backend = Path(__file__).resolve().parents[2]
    up = subprocess.run(["alembic", "upgrade", "head"], cwd=backend, env=env,
                        capture_output=True, text=True)
    assert up.returncode == 0, up.stderr
    down = subprocess.run(["alembic", "downgrade", "-1"], cwd=backend, env=env,
                          capture_output=True, text=True)
    assert down.returncode == 0, down.stderr
    up2 = subprocess.run(["alembic", "upgrade", "head"], cwd=backend, env=env,
                         capture_output=True, text=True)
    assert up2.returncode == 0, up2.stderr
```

> 实现者注：本测试可能与既有迁移测试风格不同——若仓库已有迁移测试范式（见 `tests/` 中 alembic 测试），改用其范式。否则保留此 subprocess 形式但**先 Read 一个既有迁移测试确认 cwd/env 写法**。也可在 Step 4 改为手动命令验证而非自动化测试（迁移正确性主要靠手动前后滚）。

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_migration_phase5b.py -q`
Expected: FAIL（head 仍是 phase5a，新表不存在或 multiple heads）。

- [ ] **Step 3a: 实现迁移**（仿 5A 模板 `20260531_0015_phase5a_notification.py`）

```python
# alembic/versions/20260531_0016_phase5b_email_storage.py
"""phase5b email + storage tables

Revision ID: phase5b_email_storage
Revises: phase5a_notification
Create Date: 2026-05-31

Phase 5B：邮件偏好 tb_notification_preference + 投递队列 tb_email_outbox。
存储子系统零迁移（DB schema 不变）。Hand-authored（MySQL prod + SQLite dev/test）。
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase5b_email_storage"
down_revision: str | Sequence[str] | None = "phase5a_notification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    ]


def _company_fk() -> sa.Column:
    return sa.Column(
        "company_id", sa.String(36),
        sa.ForeignKey("tb_company.id", ondelete="CASCADE"), nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "tb_notification_preference",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        *_ts(),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("disabled_types", sa.Text(), nullable=False, server_default="[]"),
        sa.UniqueConstraint("company_id", "user_id", name="uq_notif_pref_user"),
    )
    op.create_index("ix_tb_notification_preference_company_id",
                    "tb_notification_preference", ["company_id"])
    op.create_index("ix_tb_notification_preference_created_at",
                    "tb_notification_preference", ["created_at"])
    op.create_index("ix_tb_notification_preference_user_id",
                    "tb_notification_preference", ["user_id"])

    op.create_table(
        "tb_email_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        *_ts(),
        sa.Column("recipient_user_id", sa.String(36), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", DATETIME6, nullable=True),
        sa.Column("notification_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_tb_email_outbox_company_id", "tb_email_outbox", ["company_id"])
    op.create_index("ix_tb_email_outbox_created_at", "tb_email_outbox", ["created_at"])
    op.create_index("ix_tb_email_outbox_recipient_user_id", "tb_email_outbox",
                    ["recipient_user_id"])
    op.create_index("ix_email_outbox_status", "tb_email_outbox", ["company_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_email_outbox_status", table_name="tb_email_outbox")
    op.drop_index("ix_tb_email_outbox_recipient_user_id", table_name="tb_email_outbox")
    op.drop_index("ix_tb_email_outbox_created_at", table_name="tb_email_outbox")
    op.drop_index("ix_tb_email_outbox_company_id", table_name="tb_email_outbox")
    op.drop_table("tb_email_outbox")
    op.drop_index("ix_tb_notification_preference_user_id",
                  table_name="tb_notification_preference")
    op.drop_index("ix_tb_notification_preference_created_at",
                  table_name="tb_notification_preference")
    op.drop_index("ix_tb_notification_preference_company_id",
                  table_name="tb_notification_preference")
    op.drop_table("tb_notification_preference")
```

- [ ] **Step 3b: 注册模型** — `app/models/__init__.py` 加 import + `__all__`（仿 5A 注册 Notification 的位置）：

加 `from app.models.email_outbox import EmailOutbox` 与 `from app.models.notification_preference import NotificationPreference`（字母序），并在 `__all__` 加 `"EmailOutbox"`、`"NotificationPreference"`。

- [ ] **Step 3c: 手动验证前后滚**

Run:
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate
DATABASE_URL="sqlite:////tmp/_p5b_mig.db" alembic upgrade head
DATABASE_URL="sqlite:////tmp/_p5b_mig.db" alembic downgrade -1
DATABASE_URL="sqlite:////tmp/_p5b_mig.db" alembic upgrade head
alembic heads
rm -f /tmp/_p5b_mig.db
```
Expected: 三步均成功；`alembic heads` 输出**单 head** `phase5b_email_storage`。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_migration_phase5b.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add alembic/versions/20260531_0016_phase5b_email_storage.py app/models/__init__.py tests/unit/test_migration_phase5b.py
git commit -m "$(printf 'feat(phase-5b): migration phase5b_email_storage + model registration\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 9: notification_preference_service（CRUD + should_email 判定）

**Files:**
- Create: `app/services/notification_preference_service.py`
- Test: `tests/unit/test_notification_preference_service.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_notification_preference_service.py
"""偏好服务：黑名单语义、未建记录默认全开、全量替换。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services import notification_preference_service as svc

CO = "co-1"


def test_should_email_default_when_no_record(db: Session):
    # 未建记录 = 全默认开
    assert svc.should_email(db, CO, "u-1", "WO_ASSIGNED") is True


def test_upsert_then_get(db: Session):
    svc.upsert(db, CO, "u-1", email_enabled=True, disabled_types=["WO_STATUS_CHANGED"])
    db.commit()
    pref = svc.get(db, CO, "u-1")
    assert pref["email_enabled"] is True
    assert pref["disabled_types"] == ["WO_STATUS_CHANGED"]


def test_should_email_respects_disabled_type(db: Session):
    svc.upsert(db, CO, "u-1", email_enabled=True, disabled_types=["WO_STATUS_CHANGED"])
    db.commit()
    assert svc.should_email(db, CO, "u-1", "WO_STATUS_CHANGED") is False
    assert svc.should_email(db, CO, "u-1", "WO_ASSIGNED") is True


def test_should_email_respects_master_switch(db: Session):
    svc.upsert(db, CO, "u-1", email_enabled=False, disabled_types=[])
    db.commit()
    assert svc.should_email(db, CO, "u-1", "WO_ASSIGNED") is False


def test_upsert_is_idempotent_replace(db: Session):
    svc.upsert(db, CO, "u-1", email_enabled=True, disabled_types=["A"])
    db.commit()
    svc.upsert(db, CO, "u-1", email_enabled=False, disabled_types=["B", "C"])
    db.commit()
    pref = svc.get(db, CO, "u-1")
    assert pref["email_enabled"] is False
    assert sorted(pref["disabled_types"]) == ["B", "C"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_notification_preference_service.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# app/services/notification_preference_service.py
"""邮件通知偏好服务（Phase 5B）。黑名单语义；未建记录=全默认开。

所有查询显式按 company_id 过滤（不依赖租户事件），以便调度上下文下亦正确。
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification_preference import NotificationPreference

_DEFAULT = {"email_enabled": True, "disabled_types": []}


def _row(db: Session, company_id: str, user_id: str) -> NotificationPreference | None:
    return db.execute(
        select(NotificationPreference).where(
            NotificationPreference.company_id == company_id,
            NotificationPreference.user_id == user_id,
        )
    ).scalar_one_or_none()


def get(db: Session, company_id: str, user_id: str) -> dict:
    """返回偏好 dict；无记录返回默认（全开）。"""
    row = _row(db, company_id, user_id)
    if row is None:
        return dict(_DEFAULT)
    return {"email_enabled": row.email_enabled,
            "disabled_types": json.loads(row.disabled_types or "[]")}


def upsert(db: Session, company_id: str, user_id: str, *,
           email_enabled: bool, disabled_types: list[str]) -> NotificationPreference:
    """全量替换偏好（不 commit，由调用方提交）。"""
    row = _row(db, company_id, user_id)
    payload = json.dumps(list(dict.fromkeys(disabled_types)), ensure_ascii=False)
    if row is None:
        row = NotificationPreference(
            company_id=company_id, user_id=user_id,
            email_enabled=email_enabled, disabled_types=payload)
        db.add(row)
    else:
        row.email_enabled = email_enabled
        row.disabled_types = payload
    return row


def should_email(db: Session, company_id: str, user_id: str, type_: str) -> bool:
    """该用户该类型是否应收邮件 = 全局总闸 AND type 不在黑名单。"""
    pref = get(db, company_id, user_id)
    if not pref["email_enabled"]:
        return False
    return type_ not in pref["disabled_types"]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_notification_preference_service.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add app/services/notification_preference_service.py tests/unit/test_notification_preference_service.py
git commit -m "$(printf 'feat(phase-5b): notification preference service (blacklist semantics)\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 10: 偏好 schema + API + 挂载

**Files:**
- Create: `app/schemas/notification_preference.py`、`app/routers/notification_preferences.py`
- Modify: `app/main.py`（import + include_router）
- Test: `tests/test_notification_preferences_api.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_notification_preferences_api.py
"""偏好 API（/api/v1/notification-preferences）：仅本人、跨租户隔离。"""
from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def test_get_default_when_unset(client):
    t = _admin(client)
    r = client.get("/api/v1/notification-preferences", headers=_h(t))
    assert r.status_code == 200, r.text
    assert r.json() == {"email_enabled": True, "disabled_types": []}


def test_put_then_get(client):
    t = _admin(client)
    put = client.put("/api/v1/notification-preferences",
                     json={"email_enabled": False, "disabled_types": ["WO_ASSIGNED"]},
                     headers=_h(t))
    assert put.status_code == 200, put.text
    got = client.get("/api/v1/notification-preferences", headers=_h(t)).json()
    assert got["email_enabled"] is False
    assert got["disabled_types"] == ["WO_ASSIGNED"]


def test_requires_auth(client):
    assert client.get("/api/v1/notification-preferences").status_code == 401
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_notification_preferences_api.py -q`
Expected: FAIL（404，路由未挂载）

- [ ] **Step 3a: schema**

```python
# app/schemas/notification_preference.py
"""偏好读写 schema（Phase 5B）。"""
from __future__ import annotations

from pydantic import BaseModel


class NotificationPreferenceRead(BaseModel):
    email_enabled: bool
    disabled_types: list[str]


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool
    disabled_types: list[str]
```

- [ ] **Step 3b: router**

```python
# app/routers/notification_preferences.py
"""邮件通知偏好 API。个人数据：仅本人，无需额外权限码。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.notification_preference import (
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
)
from app.services import notification_preference_service as svc

router = APIRouter(prefix="/api/v1/notification-preferences", tags=["notification-preferences"])


@router.get("", response_model=NotificationPreferenceRead)
def get_preference(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    pref = svc.get(db, current_user.company_id, current_user.id)
    return NotificationPreferenceRead(**pref)


@router.put("", response_model=NotificationPreferenceRead)
def put_preference(
    payload: NotificationPreferenceUpdate,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    svc.upsert(db, current_user.company_id, current_user.id,
               email_enabled=payload.email_enabled,
               disabled_types=payload.disabled_types)
    db.commit()
    pref = svc.get(db, current_user.company_id, current_user.id)
    return NotificationPreferenceRead(**pref)
```

- [ ] **Step 3c: 挂载** — `app/main.py`：在 router import 块（5A `notifications` 行旁）加 `notification_preferences`，并在 include 区加 `app.include_router(notification_preferences.router)`。用 Edit 精确替换。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_notification_preferences_api.py -q`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add app/schemas/notification_preference.py app/routers/notification_preferences.py app/main.py tests/test_notification_preferences_api.py
git commit -m "$(printf 'feat(phase-5b): notification preference API (self-only)\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 11: EmailBackend 协议 + Console/Memory/SMTP + 工厂

**Files:**
- Create: `app/email/__init__.py`、`app/email/backends.py`
- Test: `tests/unit/test_email_backends.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_email_backends.py
"""EmailBackend 三实现（Phase 5B）。"""
from __future__ import annotations

import pytest

from app.email import get_email_backend, reset_email_backend
from app.email.backends import MemoryBackend


def test_memory_backend_collects():
    b = MemoryBackend()
    b.send("a@x.com", "subj", "body", from_addr="no-reply@x")
    assert b.sent == [("a@x.com", "subj", "body", "no-reply@x")]


def test_factory_memory(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "email_backend", "memory")
    reset_email_backend()
    assert isinstance(get_email_backend(), MemoryBackend)
    reset_email_backend()


def test_factory_console_default(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "email_backend", "console")
    reset_email_backend()
    b = get_email_backend()
    b.send("a@x.com", "s", "b", from_addr="f")  # 不抛即可
    reset_email_backend()


def test_smtp_backend_calls_smtplib(monkeypatch):
    from app.email.backends import SMTPBackend
    sent = {}

    class _FakeSMTP:
        def __init__(self, host, port): sent["addr"] = (host, port)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): sent["tls"] = True
        def login(self, u, p): sent["login"] = (u, p)
        def send_message(self, msg): sent["msg"] = msg

    monkeypatch.setattr("app.email.backends.smtplib.SMTP", _FakeSMTP)
    SMTPBackend(host="h", port=25, user="u", password="p", use_tls=True).send(
        "a@x.com", "s", "b", from_addr="f@x")
    assert sent["addr"] == ("h", 25)
    assert sent["tls"] is True
    assert sent["login"] == ("u", "p")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_email_backends.py -q`
Expected: FAIL（`ModuleNotFoundError: app.email`）

- [ ] **Step 3: 实现**

```python
# app/email/backends.py
"""邮件投递后端（Phase 5B）：SMTP（生产）/ Console（开发）/ Memory（测试）。"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

logger = logging.getLogger(__name__)


class EmailBackend(Protocol):
    def send(self, to: str, subject: str, body: str, *, from_addr: str) -> None:
        """投递一封邮件；失败抛异常。"""
        ...


class MemoryBackend:
    """测试用：把发送件收集到列表。"""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str, str]] = []

    def send(self, to: str, subject: str, body: str, *, from_addr: str) -> None:
        self.sent.append((to, subject, body, from_addr))


class ConsoleBackend:
    """开发用：渲染信息打印到日志。"""

    def send(self, to: str, subject: str, body: str, *, from_addr: str) -> None:
        logger.info("EMAIL to=%s from=%s subject=%s", to, from_addr, subject)


class SMTPBackend:
    """生产用：stdlib smtplib。"""

    def __init__(self, *, host: str, port: int, user: str, password: str,
                 use_tls: bool) -> None:
        self._host, self._port = host, port
        self._user, self._password = user, password
        self._use_tls = use_tls

    def send(self, to: str, subject: str, body: str, *, from_addr: str) -> None:
        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self._host, self._port) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._user:
                smtp.login(self._user, self._password)
            smtp.send_message(msg)
```

```python
# app/email/__init__.py
"""邮件后端工厂（Phase 5B）。按 settings.email_backend 返回单例。"""
from __future__ import annotations

from app.config import settings
from app.email.backends import (
    ConsoleBackend,
    EmailBackend,
    MemoryBackend,
    SMTPBackend,
)

_backend: EmailBackend | None = None


def get_email_backend() -> EmailBackend:
    global _backend
    if _backend is None:
        _backend = _build()
    return _backend


def reset_email_backend() -> None:
    global _backend
    _backend = None


def _build() -> EmailBackend:
    kind = settings.email_backend
    if kind == "smtp":
        return SMTPBackend(host=settings.smtp_host, port=settings.smtp_port,
                           user=settings.smtp_user, password=settings.smtp_password,
                           use_tls=settings.smtp_use_tls)
    if kind == "memory":
        return MemoryBackend()
    return ConsoleBackend()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_email_backends.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add app/email/ tests/unit/test_email_backends.py
git commit -m "$(printf 'feat(phase-5b): EmailBackend protocol + SMTP/Console/Memory\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 12: 邮件模板（type + params → subject/body）

**Files:**
- Create: `app/email/templates.py`
- Test: `tests/unit/test_email_templates.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_email_templates.py
"""邮件渲染：9 种类型按 params 出 (subject, body)。"""
from __future__ import annotations

from app.email.templates import render


def test_wo_assigned():
    subj, body = render("WO_ASSIGNED", {"custom_id": "WO1", "title": "换油"})
    assert "WO1" in subj
    assert "换油" in body


def test_unknown_type_falls_back():
    subj, body = render("SOMETHING_NEW", {"custom_id": "X"})
    assert subj  # 非空，不抛
    assert isinstance(body, str)


def test_part_low_stock():
    subj, body = render("PART_LOW_STOCK",
                        {"custom_id": "P1", "name": "滤芯", "quantity": "2", "min_quantity": "5"})
    assert "P1" in subj or "滤芯" in subj
    assert "5" in body
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_email_templates.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# app/email/templates.py
"""邮件文案模板（Phase 5B）。type + params → (subject, body)，纯函数。

文案用 default_locale（zh-CN）。params 来自 5A notify() 的结构化负载。
未知类型走通用回退（防御性，不抛）。
"""
from __future__ import annotations


def render(type_: str, params: dict) -> tuple[str, str]:
    fn = _TEMPLATES.get(type_, _fallback)
    return fn(params)


def _g(params: dict, key: str, default: str = "") -> str:
    v = params.get(key, default)
    return str(v) if v is not None else default


def _wo_assigned(p: dict) -> tuple[str, str]:
    cid, title = _g(p, "custom_id"), _g(p, "title")
    return (f"[工单] 已指派给你：{cid}",
            f"工单 {cid}「{title}」已指派给你，请及时处理。")


def _wo_status_changed(p: dict) -> tuple[str, str]:
    cid = _g(p, "custom_id")
    return (f"[工单] 状态变更：{cid}",
            f"工单 {cid} 状态由 {_g(p, 'from_status')} 变为 {_g(p, 'to_status')}。")


def _wo_auto_generated(p: dict) -> tuple[str, str]:
    cid, title = _g(p, "custom_id"), _g(p, "title")
    return (f"[工单] 自动生成：{cid}", f"系统自动生成工单 {cid}「{title}」。")


def _wo_due_soon(p: dict) -> tuple[str, str]:
    cid = _g(p, "custom_id")
    return (f"[工单] 即将到期：{cid}",
            f"工单 {cid}「{_g(p, 'title')}」将于 {_g(p, 'due_date')} 到期。")


def _wo_overdue(p: dict) -> tuple[str, str]:
    cid = _g(p, "custom_id")
    return (f"[工单] 已逾期：{cid}",
            f"工单 {cid}「{_g(p, 'title')}」已于 {_g(p, 'due_date')} 逾期。")


def _request_submitted(p: dict) -> tuple[str, str]:
    cid, title = _g(p, "custom_id"), _g(p, "title")
    return (f"[请求] 待审批：{cid}", f"请求 {cid}「{title}」已提交，等待审批。")


def _po_submitted(p: dict) -> tuple[str, str]:
    cid = _g(p, "custom_id")
    return (f"[采购单] 待审批：{cid}", f"采购单 {cid} 已提交，等待审批。")


def _po_approved(p: dict) -> tuple[str, str]:
    cid = _g(p, "custom_id")
    return (f"[采购单] 已审批：{cid}", f"采购单 {cid} 已审批通过。")


def _part_low_stock(p: dict) -> tuple[str, str]:
    cid, name = _g(p, "custom_id"), _g(p, "name")
    return (f"[库存] 低库存告警：{name}（{cid}）",
            f"备件 {name}（{cid}）当前库存 {_g(p, 'quantity')}，"
            f"低于最小库存 {_g(p, 'min_quantity')}。")


def _fallback(p: dict) -> tuple[str, str]:
    return ("[通知] 你有一条新通知", f"详情：{p}")


_TEMPLATES = {
    "WO_ASSIGNED": _wo_assigned,
    "WO_STATUS_CHANGED": _wo_status_changed,
    "WO_AUTO_GENERATED": _wo_auto_generated,
    "WO_DUE_SOON": _wo_due_soon,
    "WO_OVERDUE": _wo_overdue,
    "REQUEST_SUBMITTED": _request_submitted,
    "PO_SUBMITTED": _po_submitted,
    "PO_APPROVED": _po_approved,
    "PART_LOW_STOCK": _part_low_stock,
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_email_templates.py -q`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add app/email/templates.py tests/unit/test_email_templates.py
git commit -m "$(printf 'feat(phase-5b): email templates for 9 notification types\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 13: email_outbox_service.enqueue + 收进 notify()（同事务原子）

**Files:**
- Create: `app/services/email_outbox_service.py`（enqueue）
- Modify: `app/services/notification_service.py`（`notify()` 末尾调 enqueue）
- Test: `tests/unit/test_email_enqueue.py`（新建）+ 全量 5A 回归

> **关键**：`notify()` 现签名为 `notify(db, *, company_id, recipient_ids, type, entity_type, entity_id, params, actor_user_id=None, dedup_key=None) -> int`（见 `notification_service.py:25`）。在循环写完 Notification 后追加 enqueue。enqueue 必须**对没有 User 行 / 无 email 的 recipient 安全跳过**（5A 部分服务测试用裸 id 无 User 行）——否则破坏 5A 回归。

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_email_enqueue.py
"""notify() 内联 enqueue：按偏好生成 outbox，邮箱快照，无 User 行则跳过。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.email_outbox import EmailOutbox
from app.models.user import User, UserStatus
from app.services import notification_preference_service as pref
from app.services import notification_service as notif

CO = "co-1"


def _user(db, uid, email):
    db.add(User(id=uid, email=email, password_hash="x", name=uid,
                status=UserStatus.active, company_id=CO))
    db.commit()


def test_enqueue_for_user_with_email(db: Session):
    _user(db, "u-1", "u1@x.com")
    notif.notify(db, company_id=CO, recipient_ids={"u-1"}, type="WO_ASSIGNED",
                 entity_type="work_order", entity_id="wo-1",
                 params={"custom_id": "WO1", "title": "t"}, actor_user_id=None)
    db.commit()
    rows = db.execute(select(EmailOutbox)).scalars().all()
    assert len(rows) == 1
    assert rows[0].recipient_email == "u1@x.com"
    assert rows[0].status == "pending"
    assert rows[0].subject  # 已渲染


def test_no_user_row_skips_enqueue(db: Session):
    # 裸 id 无 User 行（5A 服务测试常见）→ 不写 outbox、不报错
    notif.notify(db, company_id=CO, recipient_ids={"ghost"}, type="WO_ASSIGNED",
                 entity_type="work_order", entity_id="wo-1",
                 params={"custom_id": "WO1"}, actor_user_id=None)
    db.commit()
    assert db.execute(select(EmailOutbox)).scalars().all() == []


def test_disabled_type_skips_enqueue(db: Session):
    _user(db, "u-1", "u1@x.com")
    pref.upsert(db, CO, "u-1", email_enabled=True, disabled_types=["WO_ASSIGNED"])
    db.commit()
    notif.notify(db, company_id=CO, recipient_ids={"u-1"}, type="WO_ASSIGNED",
                 entity_type="work_order", entity_id="wo-1",
                 params={"custom_id": "WO1"}, actor_user_id=None)
    db.commit()
    assert db.execute(select(EmailOutbox)).scalars().all() == []


def test_master_switch_off_skips(db: Session):
    _user(db, "u-1", "u1@x.com")
    pref.upsert(db, CO, "u-1", email_enabled=False, disabled_types=[])
    db.commit()
    notif.notify(db, company_id=CO, recipient_ids={"u-1"}, type="WO_ASSIGNED",
                 entity_type="work_order", entity_id="wo-1",
                 params={"custom_id": "WO1"}, actor_user_id=None)
    db.commit()
    assert db.execute(select(EmailOutbox)).scalars().all() == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_email_enqueue.py -q`
Expected: FAIL（enqueue 未接入，outbox 为空）

- [ ] **Step 3a: 实现 enqueue 服务**

```python
# app/services/email_outbox_service.py
"""邮件 outbox 入队 + 投递（Phase 5B）。

enqueue：在 notify() 内部按偏好为每个有邮箱的活跃收件人写一条 pending 行
（同事务，不 commit）。渲染在入队时完成并落库（subject/body 快照）。
所有查询显式按 company_id 过滤。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.email.templates import render
from app.models.email_outbox import EmailOutbox
from app.models.user import User, UserStatus
from app.services import notification_preference_service as pref


def enqueue(db: Session, *, company_id: str, recipient_ids: set[str], type: str,
            params: dict, notification_id: str | None = None) -> int:
    """为应收邮件的收件人写 pending outbox 行。返回入队数。不 commit。"""
    if not recipient_ids:
        return 0
    rows = db.execute(
        select(User.id, User.email).where(
            User.company_id == company_id, User.id.in_(recipient_ids),
            User.status == UserStatus.active,
        )
    ).all()
    subject, body = render(type, params)
    count = 0
    for uid, email in rows:
        if not email:
            continue
        if not pref.should_email(db, company_id, uid, type):
            continue
        db.add(EmailOutbox(
            company_id=company_id, recipient_user_id=uid, recipient_email=email,
            type=type, subject=subject, body=body, status="pending",
            notification_id=notification_id,
        ))
        count += 1
    return count
```

- [ ] **Step 3b: 收进 notify()** — `app/services/notification_service.py`，在 `notify()` 的 for 循环之后、`return count` 之前追加 enqueue。用 Edit 精确替换：

old_string:
```python
    payload = json.dumps(params, ensure_ascii=False, default=str)
    count = 0
    for uid in recipient_ids:
        db.add(Notification(
            company_id=company_id, recipient_user_id=uid, type=type,
            entity_type=entity_type, entity_id=entity_id, params=payload,
            actor_user_id=actor_user_id, dedup_key=dedup_key,
        ))
        count += 1
    return count
```
new_string:
```python
    payload = json.dumps(params, ensure_ascii=False, default=str)
    count = 0
    for uid in recipient_ids:
        db.add(Notification(
            company_id=company_id, recipient_user_id=uid, type=type,
            entity_type=entity_type, entity_id=entity_id, params=payload,
            actor_user_id=actor_user_id, dedup_key=dedup_key,
        ))
        count += 1
    # Phase 5B：同事务内按偏好为有邮箱的活跃收件人入队邮件（附加式，不 commit）。
    from app.services import email_outbox_service
    email_outbox_service.enqueue(db, company_id=company_id, recipient_ids=set(recipient_ids),
                                 type=type, params=params)
    return count
```

> 函数内 import `email_outbox_service` 是为避免模块级循环依赖（email_outbox_service → notification_preference_service，与 notification_service 无环，但函数内 import 最稳妥，仿既有 work_order_execution_service 按需 import 模式）。

- [ ] **Step 4: 跑测试 + 全量 5A 回归**

Run: `pytest tests/unit/test_email_enqueue.py tests/unit/test_notification_service.py tests/unit/test_notification_events.py tests/unit/test_notify_hook_work_order.py tests/unit/test_notify_hook_approval.py tests/unit/test_notify_hook_autogen.py -q`
Expected: 全 PASS（新 4 测 + 5A 全部仍绿——证明 enqueue 对无 User 行的旧测试无副作用）。

- [ ] **Step 5: 提交**

```bash
git add app/services/email_outbox_service.py app/services/notification_service.py tests/unit/test_email_enqueue.py
git commit -m "$(printf 'feat(phase-5b): enqueue email outbox inside notify() (atomic, pref-gated)\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 14: 投递 tick + 调度注册

**Files:**
- Modify: `app/services/email_outbox_service.py`（加 `deliver_pending` tick 逻辑）
- Create: `app/tasks/email_dispatch.py`
- Modify: `app/tasks/scheduler.py`（注册 email_dispatch job）
- Modify: `tests/unit/test_tasks.py`（job 数 5→6）
- Test: `tests/unit/test_email_dispatch.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_email_dispatch.py
"""投递 tick：pending→sent；失败累加 attempts；达上限→failed；跨租户。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.email.backends import MemoryBackend
from app.models.email_outbox import EmailOutbox
from app.tasks import email_dispatch

CO = "co-1"


def _pending(db, cid=CO, email="a@x.com"):
    o = EmailOutbox(company_id=cid, recipient_user_id="u-1", recipient_email=email,
                    type="WO_ASSIGNED", subject="s", body="b", status="pending")
    db.add(o)
    db.commit()
    return o


def test_delivers_pending_marks_sent(db: Session):
    _pending(db)
    backend = MemoryBackend()
    summary = email_dispatch.run(db, backend=backend)
    assert summary["sent"] == 1
    row = db.execute(select(EmailOutbox)).scalar_one()
    assert row.status == "sent"
    assert row.sent_at is not None
    assert backend.sent[0][0] == "a@x.com"


def test_failure_increments_attempts(db: Session):
    _pending(db)

    class _Boom:
        def send(self, *a, **k): raise RuntimeError("smtp down")

    summary = email_dispatch.run(db, backend=_Boom(), max_attempts=5)
    assert summary["failed_attempt"] == 1
    row = db.execute(select(EmailOutbox)).scalar_one()
    assert row.status == "pending"  # 未达上限，留待重试
    assert row.attempts == 1
    assert "smtp down" in row.last_error


def test_reaches_max_attempts_marks_failed(db: Session):
    o = _pending(db)
    o.attempts = 4
    db.commit()

    class _Boom:
        def send(self, *a, **k): raise RuntimeError("x")

    email_dispatch.run(db, backend=_Boom(), max_attempts=5)
    row = db.execute(select(EmailOutbox)).scalar_one()
    assert row.attempts == 5
    assert row.status == "failed"


def test_sent_rows_not_redelivered(db: Session):
    o = _pending(db)
    o.status = "sent"
    db.commit()
    backend = MemoryBackend()
    summary = email_dispatch.run(db, backend=backend)
    assert summary["sent"] == 0
    assert backend.sent == []
```

```python
# 追加到 tests/unit/test_tasks.py：把 test_scheduler_has_five_jobs 改名+加 email_dispatch
def test_scheduler_has_six_jobs() -> None:
    sched = scheduler.build_scheduler()
    job_ids = {j.id for j in sched.get_jobs()}
    assert job_ids == {"cleanup_uploads", "asset_gc", "cleanup_attachments",
                       "pm_generate", "due_reminder", "email_dispatch"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/unit/test_email_dispatch.py tests/unit/test_tasks.py -q`
Expected: FAIL（`email_dispatch` 模块不存在；scheduler 仍 5 job）

- [ ] **Step 3a: 投递逻辑** — 在 `app/services/email_outbox_service.py` 追加：

```python
def deliver_pending(db: Session, *, backend, max_attempts: int,
                    company_id: str) -> dict[str, int]:
    """投递某租户 pending 行（不 commit；由 tick 统一 commit）。"""
    from app.models.base import utcnow
    rows = db.execute(
        select(EmailOutbox).where(
            EmailOutbox.company_id == company_id,
            EmailOutbox.status == "pending",
            EmailOutbox.attempts < max_attempts,
        )
    ).scalars().all()
    sent = failed = 0
    for row in rows:
        try:
            backend.send(row.recipient_email, row.subject, row.body,
                         from_addr=_from_addr())
            row.status = "sent"
            row.sent_at = utcnow()
            sent += 1
        except Exception as e:  # noqa: BLE001 — 投递失败计数重试，不中断队列
            row.attempts += 1
            row.last_error = str(e)
            if row.attempts >= max_attempts:
                row.status = "failed"
            failed += 1
    return {"sent": sent, "failed_attempt": failed}


def _from_addr() -> str:
    from app.config import settings
    return settings.email_from
```

并在文件顶部已 import `select`/`Session`（确认）。

- [ ] **Step 3b: tick** — `app/tasks/email_dispatch.py`（仿 `due_reminder.py` 跨租户结构）：

```python
# app/tasks/email_dispatch.py
"""邮件投递调度任务（Phase 5B）。

bypass_tenant_scope 扫所有租户 pending outbox，逐租户 set_current_company_id 后投递。
sent/failed 不再被扫，天然幂等。CLI：python -m app.tasks.email_dispatch
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.email import get_email_backend
from app.logging_config import configure_logging
from app.models.email_outbox import EmailOutbox
from app.services import email_outbox_service
from app.tenant import (
    bypass_tenant_scope,
    reset_current_company_id,
    set_current_company_id,
)

logger = logging.getLogger(__name__)
TASK_NAME = "email_dispatch"


def run(db: Session, *, backend=None, max_attempts: int | None = None) -> dict[str, int]:
    backend = backend if backend is not None else get_email_backend()
    max_attempts = max_attempts if max_attempts is not None else settings.email_max_attempts

    with bypass_tenant_scope():
        company_ids = {
            cid for (cid,) in db.execute(
                select(EmailOutbox.company_id).where(EmailOutbox.status == "pending").distinct()
            ).all()
        }

    total = {"sent": 0, "failed_attempt": 0}
    for cid in company_ids:
        token = set_current_company_id(cid)
        try:
            res = email_outbox_service.deliver_pending(
                db, backend=backend, max_attempts=max_attempts, company_id=cid)
            total["sent"] += res["sent"]
            total["failed_attempt"] += res["failed_attempt"]
        finally:
            reset_current_company_id(token)

    db.commit()
    logger.info(json.dumps({"task": TASK_NAME, **total}, ensure_ascii=False))
    return total


def main() -> None:  # pragma: no cover
    configure_logging()
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    main()
```

> 注：测试 `test_email_dispatch.py` 直接传 `backend=` 且数据在同一租户上下文（无 company scoping 干扰，因测试 db 不挂租户事件或 CO 固定）。`run()` 的跨租户扫描在 `bypass_tenant_scope` 下取 distinct company_id——与 `due_reminder` 一致。

- [ ] **Step 3c: 注册调度** — `app/tasks/scheduler.py`：import 加 `email_dispatch`，加 `_run_email_dispatch()` wrapper，`build_scheduler()` 加 `add_job(_run_email_dispatch, IntervalTrigger(minutes=5), id="email_dispatch", replace_existing=True)`。用 Edit 精确替换（仿 `_run_due_reminder` 三处）。

- [ ] **Step 3d:** 把 `tests/unit/test_tasks.py` 的 `test_scheduler_has_five_jobs` 改名为 `test_scheduler_has_six_jobs` 并加入 `"email_dispatch"`（Step 1 已给出代码，用 Edit 替换该函数）。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/unit/test_email_dispatch.py tests/unit/test_tasks.py -q`
Expected: 全 PASS（新 4 测 + scheduler 6-job 测）。

- [ ] **Step 5: 提交**

```bash
git add app/services/email_outbox_service.py app/tasks/email_dispatch.py app/tasks/scheduler.py tests/unit/test_email_dispatch.py tests/unit/test_tasks.py
git commit -m "$(printf 'feat(phase-5b): email dispatch tick + scheduler registration\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 15: 收尾 — 全量回归 / ruff / alembic / Atlas / 记忆

**Files:** 无新增代码（除非修缺陷）。

- [ ] **Step 1: 清缓存 + 全量回归**

Run:
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate
find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache
PYTHONDONTWRITEBYTECODE=1 pytest -q
```
Expected: **0 failed**（基线 1077 + 本期新增 ~35–40）。若有失败逐一修；尤其留意 enqueue 对既有 5A/附件/asset 测试的副作用。

- [ ] **Step 2: ruff**

Run: `ruff check app/storage_backends app/email app/models/email_outbox.py app/models/notification_preference.py app/services/email_outbox_service.py app/services/notification_preference_service.py app/routers/notification_preferences.py app/tasks/email_dispatch.py app/services/notification_service.py app/services/asset_service.py app/services/attachment_service.py app/services/source_docx_service.py app/config.py app/main.py app/tasks/scheduler.py`
Expected: `All checks passed!`（若 I001 import 排序，`ruff check --fix` 后重提交对应文件）。

- [ ] **Step 3: alembic 单 head**

Run: `alembic heads`
Expected: 单 head `phase5b_email_storage`。

- [ ] **Step 4: Atlas 扫描**

Run: `grep -rin "atlas" app/ alembic/versions/20260531_0016_phase5b_email_storage.py docs/superpowers/specs/2026-05-31-phase-5b-email-storage-design.md docs/superpowers/plans/2026-05-31-phase-5b-email-storage.md ; echo "exit=$?"`
Expected: 无业务命中（exit=1 表示无匹配即合格）。

- [ ] **Step 5: 工作树纪律核查**

Run: `git status --porcelain`
Expected: 仅本期已提交内容；若有非本期游离改动（其他会话遗留），**不提交不 revert**，原样保留。

- [ ] **Step 6: 写项目记忆** — 新建 `/Users/yuming/.claude/projects/-Users-yuming-Desktop-smart-CMMS/memory/phase-5b-status.md`（镜像 phase-5a-status 格式：范围/2 表/邮件 outbox+偏好/存储后端收口+source_docx 目录清理本地限制/迁移单 head/测试数/提交链/执行方式），并在 `MEMORY.md` 索引追加一行 Phase 5B（5A 行之后）。**注意 source_docx 孤儿目录清理仅 local 后端有效这一限制要明确写入（no silent caps）。**

- [ ] **Step 7: 最终汇报** — 向用户简报完成情况与提交链。

---

## Self-Review（写计划后自检结论）

- **Spec 覆盖**：A3 偏好/outbox 表 → Task 7/8；A4 模板 → Task 12；A5 EmailBackend → Task 11；A6.1 enqueue 收进 notify → Task 13；A6.2 投递 tick+调度 → Task 14；A7 偏好 API → Task 10；B3/B4 StorageBackend+Local+S3 → Task 2/3；B5 三类消费方收口 → Task 4/5/6；§8 配置 → Task 1；§9 迁移 → Task 8；§10 RBAC/租户/跨方言 → Task 10/14 测试；§11 测试矩阵 → 各 task 测试 + Task 15 回归。**无缺口。**
- **Spec 修正（plan 比 spec 更细之处）**：B5 的 source_docx **目录枚举型孤儿清理**（`orphan_group_ids`/`delete_group_dir`/`sweep_source_docx`）不映射最小接口 → 计划明确保持本地 FS、仅 local 后端有效，并要求写入注释与 status。这是对 spec「source_docx 走后端」的精确化（per-file IO 走后端，目录清理留本地），需在交付时向用户点出。
- **类型/签名一致性**：`get_storage_backend()`/`reset_storage_backend()`、`get_email_backend()`/`reset_email_backend()`、`EmailBackend.send(to, subject, body, *, from_addr)`、`notification_preference_service.{get,upsert,should_email}`、`email_outbox_service.{enqueue,deliver_pending}`、`email_dispatch.run(db, *, backend, max_attempts)`、`templates.render(type_, params)` 全计划内自洽。
- **占位符扫描**：Task 4/6 中 `asset_service.load` / `get_for_procedure` 调用方等标注「执行前 Read 确认真实名」——非占位，是对既有代码动态锚点的显式校验要求（行号可能漂移）。
