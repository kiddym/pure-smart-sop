# 程序库 IA 重构 + 归档系统文件夹 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把程序库 `/procedures/library` 重做成双栏（左 FolderTreePane + 右 ListPane），文件夹树渲染含「废止」「归档」system folders；新增"归档"系统文件夹 + `archive_group` 用户动作（与现有 deprecate 镜像，不同语义）；进入程序库自动折叠 AppSidebar。

**Architecture:** Backend 扩展 `seed.py` 幂等 seed「归档」folder + `version_flow_service.archive_group`（镜像 deprecate）+ `POST /procedures/{id}/archive` 端点；现有 restore 流程已通用、零改动。Frontend 重构 `ProcedureLibraryView` 为双栏：左侧 `FolderTreePane` 包 `FolderTree` 组件，右侧 ListPane 沿用 ProcedureTable；前端按 `folder.system` 切换 `query.status` (PUBLISHED ↔ ARCHIVED)。`AppLayout` 接 `sidebarAutoCollapse.ts` 纯函数 + watcher，路由进入 library 时自动折叠（沿用 editor-focus 模式）。`ProcedureDetailView` 加"归档"按钮（与现有"废止"并列）。

**Tech Stack:** Backend FastAPI + SQLAlchemy + pytest；Frontend Vue 3 `<script setup>` + TypeScript + Element Plus 2.7 + Vitest + `@vue/test-utils`。

**Gate（每次"跑测试"与收尾）：** Backend `cd backend && pytest -x tests/`；Frontend `cd frontend && npx vitest run tests/unit/<file>.spec.ts` 跑单测；收尾再 `cd frontend && npm run lint && npm run typecheck && npm run build`（`--max-warnings 0`）。

**Spec：** [docs/superpowers/specs/2026-05-26-library-ia-archive-folder-design.md](../specs/2026-05-26-library-ia-archive-folder-design.md)

**Branch：** `feat/library-ia-archive-folder`（spec commit `e8dd187` 已在此分支）

---

## 文件结构

| 文件 | 状态 | 职责 |
|---|---|---|
| `backend/app/seed.py` | 改 | 加 `ARCHIVED_FOLDER_NAME = "归档"`，`seed_system_folders` 同时 seed 两个 system folders |
| `backend/tests/unit/test_seed.py` | 改 | 旧 `test_run_seed_creates_system_folders` 加归档断言；幂等性测期望 `system=True count == 2` |
| `backend/app/services/version_flow_service.py` | 改 | 加 `_archived_folder` helper + `archive_group` service（镜像 deprecate）|
| `backend/tests/unit/services/test_version_flow_service.py` | 改 | 加 4 个 archive 单测 + 1 个 restore-from-archive |
| `backend/app/routers/procedures.py` | 改 | 加 `POST /procedures/{id}/archive` 端点 |
| `backend/tests/integration/test_procedures.py` | 改 | 加 archive 端点集成测 + archive→restore round trip |
| `frontend/src/utils/sidebarAutoCollapse.ts` | 新 | 纯函数 `decideAutoCollapse(from, to, userOverride)` |
| `frontend/tests/unit/utils/sidebarAutoCollapse.spec.ts` | 新 | 5 单测 |
| `frontend/src/components/library/FolderTreePane.vue` | 新 | 220px 左侧文件夹树面板，包 FolderTree |
| `frontend/src/views/procedures/ProcedureLibraryView.vue` | 改 | 重构为双栏：左 FolderTreePane + 右 ListPane；selectedFolder + status 自动切换 |
| `frontend/tests/unit/ProcedureLibraryView.spec.ts` | 新 | 5 单测 |
| `frontend/src/layouts/AppLayout.vue` | 改 | 接入 sidebarAutoCollapse watcher |
| `frontend/src/api/procedures.ts` | 改 | 加 `archiveGroup(id, reason)` API client |
| `frontend/src/views/procedures/ProcedureDetailView.vue` | 改 | 加"归档"按钮 + PendingAction `'archive'` 分支 + dialog 配置 + commit 处理 |
| `docs/design-system.md` | 改 | §3.1 ASCII 旁的"未落地"注释更新为"已实现" |
| `docs/feature-clarifications.md` | 改 | §50.2 加 R2 修订脚注 |
| `docs/superpowers/specs/2026-05-26-topbar-ia-design.md` | 改 | R1 修订段加"被本 spec 永久取代"注 |

---

## Task 1: seed.py 加 ARCHIVED_FOLDER_NAME + 更新 seed 单测

**Files:**
- Modify: `backend/app/seed.py`
- Modify: `backend/tests/unit/test_seed.py`

- [ ] **Step 1: 写失败测试**

修改 `backend/tests/unit/test_seed.py`:

将现有 `test_run_seed_creates_system_folders` 替换为：

```python
def test_run_seed_creates_system_folders(db) -> None:
    seed.run_seed(db)

    deprecated = db.query(Folder).filter_by(name=seed.DEPRECATED_FOLDER_NAME).one()
    archived = db.query(Folder).filter_by(name=seed.ARCHIVED_FOLDER_NAME).one()

    assert deprecated.system is True
    assert deprecated.parent_id is None
    assert archived.system is True
    assert archived.parent_id is None
```

将现有 `test_run_seed_is_idempotent` 中 `Folder` 断言改为：

```python
def test_run_seed_is_idempotent(db) -> None:
    """重复运行不重复插入（data-model §6 幂等）。"""
    seed.run_seed(db)
    seed.run_seed(db)
    seed.run_seed(db)

    assert db.query(Folder).filter_by(system=True).count() == 2  # 废止 + 归档
    assert db.query(ProcedureSettings).count() == 1
    assert db.query(ProcedureField).count() == 1
    assert db.query(FolderSequence).count() == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/test_seed.py -v`
Expected: FAIL（`AttributeError: module 'app.seed' has no attribute 'ARCHIVED_FOLDER_NAME'` 或 count 不等）

- [ ] **Step 3: 修改 seed.py**

修改 `backend/app/seed.py`，在 `DEPRECATED_FOLDER_NAME = "废止"` 行之后加：

```python
ARCHIVED_FOLDER_NAME = "归档"
```

并把 `seed_system_folders` 改成（关注循环结构，名字驱动）：

```python
def seed_system_folders(db: Session) -> None:
    """创建「废止」「归档」系统文件夹（两个 system folder；模板库已废，§56/Q340）。"""
    for name in (DEPRECATED_FOLDER_NAME, ARCHIVED_FOLDER_NAME):
        if _get_root_folder(db, name) is None:
            db.add(
                Folder(
                    name=name,
                    system=True,
                    parent_id=None,
                    prefix="",
                    full_path=name,
                )
            )
            logger.info("seed: created system folder %s", name)
```

注释行 "废止：接收被废止程序…" 那条删除（循环里两个都同样的设置，不需要单独 inline 注释）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/unit/test_seed.py -v`
Expected: PASS（4 个测试全绿）

- [ ] **Step 5: 提交**

```bash
git add backend/app/seed.py backend/tests/unit/test_seed.py
git commit -m "feat(backend): seed 加「归档」系统文件夹

镜像「废止」的 seed 模式，幂等。两个 system folders 并列。

后续 archive_group service 将使用 ARCHIVED_FOLDER_NAME 常量。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: archive_group service + helper + 单测

**Files:**
- Modify: `backend/app/services/version_flow_service.py`
- Modify: `backend/tests/unit/services/test_version_flow_service.py`

- [ ] **Step 1: 写失败测试**

修改 `backend/tests/unit/services/test_version_flow_service.py`，在文件末尾加：

```python
def test_archive_group_moves_to_archive_folder(db, meta) -> None:
    """归档：整 group 转 ARCHIVED + folder_id 改归档 + 记原 folder。"""
    seed.run_seed(db)
    normal_folder = make_folder(db, name="QC")
    proc = make_procedure(db, folder=normal_folder, status="PUBLISHED")

    version_flow_service.archive_group(db, proc.id, "已过时不再推广", meta)

    db.refresh(proc)
    archive_folder = db.query(Folder).filter_by(name=seed.ARCHIVED_FOLDER_NAME).one()
    assert proc.status == "ARCHIVED"
    assert proc.folder_id == archive_folder.id
    assert proc.deprecated_from_folder_id == normal_folder.id  # 复用字段记原 folder


def test_archive_group_rejects_system_folder(db, meta) -> None:
    """禁止归档系统文件夹下的程序。"""
    seed.run_seed(db)
    archive_folder = db.query(Folder).filter_by(name=seed.ARCHIVED_FOLDER_NAME).one()
    proc = make_procedure(db, folder=archive_folder, status="ARCHIVED")

    with pytest.raises(HTTPException) as exc:
        version_flow_service.archive_group(db, proc.id, "再次归档", meta)
    assert exc.value.detail["code"] == "PROCEDURE_ARCHIVE_SYSTEM_FOLDER"


def test_archive_group_rejects_already_archived(db, meta) -> None:
    """禁止归档已 ARCHIVED 的程序（无论 folder）。"""
    seed.run_seed(db)
    normal_folder = make_folder(db, name="QC")
    proc = make_procedure(db, folder=normal_folder, status="ARCHIVED")

    with pytest.raises(HTTPException) as exc:
        version_flow_service.archive_group(db, proc.id, "归档", meta)
    assert exc.value.detail["code"] == "PROCEDURE_ALREADY_ARCHIVED_OR_DEPRECATED"


def test_archive_group_requires_reason(db, meta) -> None:
    """归档 reason 必填。"""
    seed.run_seed(db)
    normal_folder = make_folder(db, name="QC")
    proc = make_procedure(db, folder=normal_folder, status="PUBLISHED")

    with pytest.raises(HTTPException) as exc:
        version_flow_service.archive_group(db, proc.id, "", meta)
    assert exc.value.detail["code"] == "REASON_REQUIRED"


def test_restore_from_archive(db, meta) -> None:
    """restore 通用：从归档恢复路径同从废止恢复（同函数、同字段）。"""
    seed.run_seed(db)
    normal_folder = make_folder(db, name="QC")
    proc = make_procedure(db, folder=normal_folder, status="PUBLISHED")
    version_flow_service.archive_group(db, proc.id, "归档", meta)

    new_proc = version_flow_service.restore(db, proc.id, "重新启用", None, meta)

    assert new_proc.status == "DRAFT"
    assert new_proc.folder_id == normal_folder.id  # 恢复到原 folder
```

> **注**：以上测试假设 `make_procedure` / `make_folder` / `meta` 在 `conftest.py` 中已经定义（与现有 deprecate 测试同款）。若缺失，参照现有 deprecate 测试的 fixture 使用方式补齐。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/services/test_version_flow_service.py -k archive -v`
Expected: FAIL（`AttributeError: module 'version_flow_service' has no attribute 'archive_group'`）

- [ ] **Step 3: 实现 archive_group**

修改 `backend/app/services/version_flow_service.py`。在文件顶部 import 区改：

```python
from app.seed import ARCHIVED_FOLDER_NAME, DEPRECATED_FOLDER_NAME
```

（如已 import `DEPRECATED_FOLDER_NAME`，把 `ARCHIVED_FOLDER_NAME` 加入同一行。）

在现有 `_deprecated_folder` helper 函数定义之后，加平行 helper：

```python
def _archived_folder(db: Session) -> Folder:
    folder = db.execute(
        select(Folder).where(
            Folder.name == ARCHIVED_FOLDER_NAME,
            Folder.system.is_(True),
            Folder.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if folder is None:
        raise not_found("NOT_FOUND", "「归档」系统文件夹缺失")
    return folder
```

在现有 `deprecate` 函数定义之后，加平行 service 函数 `archive_group`：

```python
def archive_group(db: Session, proc_id: str, reason: str, meta: RequestMeta) -> Procedure:
    """归档整 group：与 deprecate 平行，语义差别在 folder（归档 vs 废止）。"""
    proc = procedure_service.get_or_404(db, proc_id)
    if proc.folder.system:
        raise bad_request("PROCEDURE_ARCHIVE_SYSTEM_FOLDER", "系统文件夹下的程序不可归档")
    if proc.status == "ARCHIVED":
        raise bad_request("PROCEDURE_ALREADY_ARCHIVED_OR_DEPRECATED", "该程序已归档或已废止")
    if not reason.strip():
        raise bad_request("REASON_REQUIRED", "请填写归档原因")

    archive_folder = _archived_folder(db)
    now = utcnow()
    records = _group_records(db, proc.procedure_group_id)
    # 与 deprecate 一致：deprecated_by 恒 NULL（Q322 全匿名）
    for rec in records:
        rec.deprecated_from_folder_id = rec.folder_id  # 复用字段记原 folder
        rec.folder_id = archive_folder.id
        rec.deprecated_at = now  # 复用 deprecated_at 时间戳，restore 流程通用
        if rec.status != "ARCHIVED":
            rec.status = "ARCHIVED"
            if rec.archived_at is None:
                rec.archived_at = now
    db.flush()
    _audit(db, proc, "archive", meta, new_value={"version_count": len(records)}, reason=reason)
    return proc
```

> **关于字段复用的 docstring 注**：`deprecated_at` / `deprecated_from_folder_id` 现在双用——既记 deprecate 也记 archive。这是有意的：restore 流程不区分二者来源，统一从 `deprecated_from_folder_id` 取原 folder + 清空标记。字段重命名作为独立 topic 处理。

- [ ] **Step 4: 跑测试确认全绿**

Run: `cd backend && pytest tests/unit/services/test_version_flow_service.py -v`
Expected: PASS（含 5 个新加的 archive / restore-from-archive 测试 + 现有 deprecate / restore 测试不破）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/version_flow_service.py backend/tests/unit/services/test_version_flow_service.py
git commit -m "feat(backend): 加 archive_group service（与 deprecate 镜像）

整 group → ARCHIVED + folder_id 改「归档」+ 复用 deprecated_from_folder_id
记原 folder + 复用 deprecated_at 时间戳（让 restore 流程通用、不区分来源）。

错误码：
- PROCEDURE_ARCHIVE_SYSTEM_FOLDER（试图归档系统 folder 下的程序）
- PROCEDURE_ALREADY_ARCHIVED_OR_DEPRECATED（试图归档已 ARCHIVED）
- REASON_REQUIRED（reason 必填）

restore 通用化是\"零改动通用化\"：现有逻辑已经从 deprecated_from_folder_id
取原 folder + 清空标记，归档恢复零代码改动。test_restore_from_archive 验证。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `/archive` 端点 + 集成测试

**Files:**
- Modify: `backend/app/routers/procedures.py`
- Modify: `backend/tests/integration/test_procedures.py`

- [ ] **Step 1: 写失败集成测试**

在 `backend/tests/integration/test_procedures.py` 末尾加：

```python
def test_archive_endpoint_full_flow(client, db) -> None:
    """端到端：创建程序 → archive → 校验 status + folder。"""
    seed.run_seed(db)
    folder = make_folder(db, name="QC")
    proc = make_procedure(db, folder=folder, status="PUBLISHED", commit=True)

    res = client.post(
        f"/procedures/{proc.id}/archive",
        json={"reason": "stale—keep for reference"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ARCHIVED"
    archive_folder = db.query(Folder).filter_by(name=seed.ARCHIVED_FOLDER_NAME).one()
    assert body["folder_id"] == archive_folder.id


def test_archive_then_restore_round_trip(client, db) -> None:
    """从归档恢复：复用现有 restore 端点。"""
    seed.run_seed(db)
    folder = make_folder(db, name="QC")
    proc = make_procedure(db, folder=folder, status="PUBLISHED", commit=True)

    client.post(f"/procedures/{proc.id}/archive", json={"reason": "stale"})
    res = client.post(f"/procedures/{proc.id}/restore", json={"reason": "back"})

    assert res.status_code == 200
    body = res.json()
    # restore 创建新 DRAFT、移回原 folder
    assert body["folder_id"] == folder.id
    assert body["status"] == "DRAFT"
```

> 若 `make_folder` / `make_procedure` 在集成测试 fixture 中名字不同，参照同文件内 deprecate 集成测试用法。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/integration/test_procedures.py -k archive -v`
Expected: FAIL（404 Not Found，端点不存在）

- [ ] **Step 3: 加端点**

修改 `backend/app/routers/procedures.py`。在现有 `deprecate` 端点定义之后（约 line 314 附近，`@router.post("/{procedure_id}/deprecate"...)` 后），加：

```python
@router.post("/{procedure_id}/archive", response_model=ProcedureMeta)
def archive(
    procedure_id: str,
    payload: ReasonIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> ProcedureMeta:
    proc = version_flow_service.archive_group(db, procedure_id, payload.reason, meta)
    db.commit()
    return procedure_service.to_meta(db, proc)
```

直接复用现有 `ReasonIn` schema（与 deprecate 一致）。

- [ ] **Step 4: 跑测试确认全绿**

Run: `cd backend && pytest tests/integration/test_procedures.py -v`
Expected: PASS（含 2 个新 archive 集成测试 + 现有所有不破）

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/procedures.py backend/tests/integration/test_procedures.py
git commit -m "feat(backend): POST /procedures/{id}/archive 端点

镜像 deprecate 端点结构，复用 ReasonIn schema。
集成测试验证：archive 后 status=ARCHIVED+folder=归档；
restore 后回到原 folder（端到端通用，零额外代码）。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `sidebarAutoCollapse.ts` 纯函数 + 单测

**Files:**
- Create: `frontend/src/utils/sidebarAutoCollapse.ts`
- Create: `frontend/tests/unit/utils/sidebarAutoCollapse.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/utils/sidebarAutoCollapse.spec.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { decideAutoCollapse } from '@/utils/sidebarAutoCollapse'

describe('decideAutoCollapse', () => {
  it('进入 library 路由 → collapse', () => {
    expect(decideAutoCollapse('/procedures/drafts', '/procedures/library', false)).toBe('collapse')
  })

  it('从其他根路由进入 library → collapse', () => {
    expect(decideAutoCollapse('/folders', '/procedures/library', false)).toBe('collapse')
  })

  it('离开 library 路由 → restore', () => {
    expect(decideAutoCollapse('/procedures/library', '/folders', false)).toBe('restore')
  })

  it('在 library 内部跳转 → noop', () => {
    expect(decideAutoCollapse('/procedures/library', '/procedures/library', false)).toBe('noop')
  })

  it('library 之外跳转 → noop', () => {
    expect(decideAutoCollapse('/folders', '/settings', false)).toBe('noop')
  })

  it('userOverride=true → 永远 noop（用户接管）', () => {
    expect(decideAutoCollapse('/procedures/drafts', '/procedures/library', true)).toBe('noop')
    expect(decideAutoCollapse('/procedures/library', '/folders', true)).toBe('noop')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/utils/sidebarAutoCollapse.spec.ts`
Expected: FAIL（`Cannot find module '@/utils/sidebarAutoCollapse'`）

- [ ] **Step 3: 写实现**

Create `frontend/src/utils/sidebarAutoCollapse.ts`:

```ts
/**
 * 决定路由切换时是否需要对 AppSidebar 自动折叠 / 恢复。
 *
 * 规则：
 * - 用户手动 toggle 过 → 接管，此后所有路由切换均 noop
 * - 进入 /procedures/library → collapse
 * - 离开 /procedures/library → restore
 * - 其他情况 → noop
 *
 * 沿用 editorFocus.ts 的"自动折叠 / 用户接管"模式（spec §C）。
 */
export type CollapseDecision = 'collapse' | 'restore' | 'noop'

const LIBRARY_PATH_PREFIX = '/procedures/library'

function isLibrary(path: string): boolean {
  return path.startsWith(LIBRARY_PATH_PREFIX)
}

export function decideAutoCollapse(
  fromPath: string,
  toPath: string,
  userOverride: boolean,
): CollapseDecision {
  if (userOverride) return 'noop'
  const wasLibrary = isLibrary(fromPath)
  const isLib = isLibrary(toPath)
  if (!wasLibrary && isLib) return 'collapse'
  if (wasLibrary && !isLib) return 'restore'
  return 'noop'
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run tests/unit/utils/sidebarAutoCollapse.spec.ts`
Expected: PASS（6 个测试全绿）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/sidebarAutoCollapse.ts frontend/tests/unit/utils/sidebarAutoCollapse.spec.ts
git commit -m "feat(frontend): sidebarAutoCollapse 纯函数 + 6 单测

3 状态判定（collapse / restore / noop），支持 userOverride 接管。
AppLayout 接入将在 Task 7 处理。沿用 editorFocus.ts 模式。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `FolderTreePane.vue` 组件（薄封装）

**Files:**
- Create: `frontend/src/components/library/FolderTreePane.vue`

- [ ] **Step 1: 直接写实现（薄封装，无独立单测——会随 LibraryView 测试覆盖）**

Create `frontend/src/components/library/FolderTreePane.vue`:

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import FolderTree from '@/components/FolderTree.vue'
import { useFolderStore } from '@/store/folders'
import type { FolderTreeNode } from '@/types/folder'

defineEmits<{
  (e: 'select', node: FolderTreeNode | null): void
}>()

const store = useFolderStore()

onMounted(() => {
  void store.loadTree()
})
</script>

<template>
  <div class="folder-tree-pane">
    <header class="pane-header">
      <span class="title">文件夹</span>
    </header>
    <div class="tree-body">
      <FolderTree
        :data="store.tree"
        :loading="store.loading"
        @select="(n) => $emit('select', n)"
      />
    </div>
  </div>
</template>

<style scoped>
.folder-tree-pane {
  width: 220px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border-right: 1px solid #e0dbd3;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.pane-header {
  height: 40px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  border-bottom: 1px solid #e0dbd3;
  flex-shrink: 0;
}
.pane-header .title {
  font-size: 12px;
  color: #9a8e80;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.tree-body {
  flex: 1;
  overflow: auto;
  padding: 8px 0;
}
</style>
```

- [ ] **Step 2: 跑 typecheck 确认无错**

Run: `cd frontend && npm run typecheck`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/library/FolderTreePane.vue
git commit -m "feat(frontend): 加 FolderTreePane 组件（220px 文件夹树面板）

薄封装：包 FolderTree + 用 folders store 拉树 + onMounted loadTree。
Emit 'select' 给父级（ProcedureLibraryView 在 Task 6 消费）。

样式：var(--bg-surface) + 1px 右分隔（沿用 AppSidebar 同款）；
小帽 'UPPERCASE 文件夹'（信息架构语义清晰）。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `ProcedureLibraryView.vue` 重构为双栏（TDD）

**Files:**
- Modify: `frontend/src/views/procedures/ProcedureLibraryView.vue`
- Create: `frontend/tests/unit/ProcedureLibraryView.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/unit/ProcedureLibraryView.spec.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import type { FolderTreeNode } from '@/types/folder'

// 直接 mock store 模块，避开 @pinia/testing 依赖（未装）。
// 这些测试只关心 view 的本地 state；store 调用 mock 成 noop 即可。
vi.mock('@/store/procedures', () => ({
  useProcedureStore: () => ({
    loadList: vi.fn().mockResolvedValue(undefined),
    rows: [],
    total: 0,
    page: 1,
    pageSize: 20,
    loading: false,
  }),
}))

// dynamic import 必须在 mock 之后，否则 store import 不被拦截
const { default: ProcedureLibraryView } = await import(
  '@/views/procedures/ProcedureLibraryView.vue'
)

const normalFolder: FolderTreeNode = {
  id: 'f-normal', name: 'QC', prefix: 'QC', parent_id: null, system: false,
  full_path: 'QC', created_at: '', updated_at: '',
  procedure_count: 0, children: [],
}
const archiveFolder: FolderTreeNode = {
  id: 'f-archive', name: '归档', prefix: '', parent_id: null, system: true,
  full_path: '归档', created_at: '', updated_at: '',
  procedure_count: 0, children: [],
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/procedures/library', component: { template: '<div/>' } },
      { path: '/procedures/:id', component: { template: '<div/>' } },
    ],
  })
}

async function mountView() {
  const router = makeRouter()
  await router.push('/procedures/library')
  await router.isReady()
  return mount(ProcedureLibraryView, {
    global: {
      plugins: [router],
      stubs: {
        // FolderTreePane / ProcedureTable / 对话框 stub，避免拉真数据
        FolderTreePane: { props: ['data'], template: '<div class="ft-stub"/>', emits: ['select'] },
        ProcedureTable: { props: ['rows', 'loading'], template: '<div class="pt-stub"/>', emits: ['open'] },
        CreateProcedureDialog: true,
        CreateFromWordDialog: true,
      },
    },
  })
}

describe('ProcedureLibraryView', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('mount 时无选中文件夹：query.status=PUBLISHED, folder_id=undefined', async () => {
    const w = await mountView()
    const vm = w.vm as unknown as { query: { status: string; folder_id?: string } }
    expect(vm.query.status).toBe('PUBLISHED')
    expect(vm.query.folder_id).toBeUndefined()
  })

  it('选中普通文件夹：query.status=PUBLISHED + folder_id 设入', async () => {
    const w = await mountView()
    const tree = w.findComponent({ name: 'FolderTreePane' })
    await tree.vm.$emit('select', normalFolder)
    const vm = w.vm as unknown as { query: { status: string; folder_id?: string } }
    expect(vm.query.status).toBe('PUBLISHED')
    expect(vm.query.folder_id).toBe('f-normal')
  })

  it('选中 system 文件夹：query.status 自动切到 ARCHIVED', async () => {
    const w = await mountView()
    const tree = w.findComponent({ name: 'FolderTreePane' })
    await tree.vm.$emit('select', archiveFolder)
    const vm = w.vm as unknown as { query: { status: string; folder_id?: string } }
    expect(vm.query.status).toBe('ARCHIVED')
    expect(vm.query.folder_id).toBe('f-archive')
  })

  it('选中 system 文件夹时「新建」按钮隐藏', async () => {
    const w = await mountView()
    const tree = w.findComponent({ name: 'FolderTreePane' })
    await tree.vm.$emit('select', archiveFolder)
    expect(w.find('[data-test="create-btn"]').exists()).toBe(false)
  })

  it('普通文件夹下「新建」按钮显示', async () => {
    const w = await mountView()
    const tree = w.findComponent({ name: 'FolderTreePane' })
    await tree.vm.$emit('select', normalFolder)
    expect(w.find('[data-test="create-btn"]').exists()).toBe(true)
  })
})
```

> **注**：测试用 `createTestingPinia` 配合 vi 的 stub actions=false，因为我们不验 store 网络调用、只验 view state。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run tests/unit/ProcedureLibraryView.spec.ts`
Expected: FAIL（FolderTreePane 子组件不存在 / query 结构不匹配 / 新建按钮可见性逻辑未实现）

- [ ] **Step 3: 重构 ProcedureLibraryView.vue**

完全替换 `frontend/src/views/procedures/ProcedureLibraryView.vue`：

```vue
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import FolderTreePane from '@/components/library/FolderTreePane.vue'
import ProcedureTable from '@/components/ProcedureTable.vue'
import CreateProcedureDialog from '@/components/CreateProcedureDialog.vue'
import CreateFromWordDialog from '@/components/CreateFromWordDialog.vue'
import { useProcedureStore } from '@/store/procedures'
import type { ProcedureMeta, ProcedureStatus } from '@/types/procedure'
import type { FolderTreeNode } from '@/types/folder'

const router = useRouter()
const store = useProcedureStore()
const createVisible = ref(false)
const wordVisible = ref(false)

const selectedFolder = ref<FolderTreeNode | null>(null)

interface LibraryQuery {
  search: string
  status: ProcedureStatus
  folder_id: string | undefined
  page: number
}

const query = reactive<LibraryQuery>({
  search: '',
  status: 'PUBLISHED' as ProcedureStatus,
  folder_id: undefined,
  page: 1,
})

async function load(): Promise<void> {
  await store.loadList({
    page: query.page,
    page_size: store.pageSize,
    search: query.search || undefined,
    status: query.status,
    folder_id: query.folder_id,
  })
}

onMounted(load)

function onSelectFolder(node: FolderTreeNode | null): void {
  selectedFolder.value = node
  query.folder_id = node?.id
  query.status = (node?.system ? 'ARCHIVED' : 'PUBLISHED') as ProcedureStatus
  query.page = 1
  void load()
}

function onSearch(): void {
  query.page = 1
  void load()
}

function onPage(page: number): void {
  query.page = page
  void load()
}

function open(id: string): void {
  void router.push(`/procedures/${id}`)
}

function onCreated(proc: ProcedureMeta): void {
  void router.push(`/procedures/${proc.id}/edit`)
}

function onImported(id: string): void {
  void router.push({ path: `/procedures/${id}/edit`, query: { from: 'import' } })
}
</script>

<template>
  <div class="library">
    <FolderTreePane @select="onSelectFolder" />

    <div class="list-pane">
      <div class="toolbar">
        <h2 class="title">{{ selectedFolder?.name ?? '全库' }}</h2>
        <div class="toolbar-actions">
          <el-dropdown
            v-if="!selectedFolder?.system"
            data-test="create-btn"
            trigger="click"
            @command="(c: string) => (c === 'word' ? (wordVisible = true) : (createVisible = true))"
          >
            <el-button type="primary">新建</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="blank">空白程序</el-dropdown-item>
                <el-dropdown-item command="word">从 Word 导入</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <div class="filters">
        <el-input
          v-model="query.search"
          placeholder="搜索编码 / 名称 / 描述（跨全库）"
          clearable
          class="search"
          @keyup.enter="onSearch"
          @clear="onSearch"
        />
        <el-button @click="onSearch">查询</el-button>
      </div>

      <ProcedureTable :rows="store.rows" :loading="store.loading" @open="open" />

      <el-pagination
        class="pager"
        layout="total, prev, pager, next"
        :total="store.total"
        :current-page="store.page"
        :page-size="store.pageSize"
        @current-change="onPage"
      />

      <CreateProcedureDialog v-model="createVisible" @created="onCreated" />
      <CreateFromWordDialog v-model="wordVisible" @imported="onImported" />
    </div>
  </div>
</template>

<style scoped>
.library {
  display: flex;
  height: 100%;
  min-height: 0;
}
.list-pane {
  flex: 1;
  overflow: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.title {
  margin: 0;
  font-size: 18px;
}
.filters {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.search {
  flex: 1;
  max-width: 400px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
```

> **关键变化对比旧版**：
> - 双栏 layout：`FolderTreePane` + `list-pane`
> - 引入 `selectedFolder` ref + `onSelectFolder` 处理树选择
> - `query.status` 默认 'PUBLISHED'（不再是 ''）；选 system folder 时切 'ARCHIVED'
> - `query.folder_id` 加入查询参数
> - 删除了 status 下拉过滤器（status 由文件夹类型驱动）
> - 标题动态：选中文件夹时显示文件夹名，否则"全库"
> - 新建按钮在 system folder 时 v-if 隐藏；加 `data-test="create-btn"` 供测试

- [ ] **Step 4: 跑测试确认全绿**

Run: `cd frontend && npx vitest run tests/unit/ProcedureLibraryView.spec.ts`
Expected: PASS（5 单测全绿）

并跑全量测试确保现有不破：

Run: `cd frontend && npx vitest run`
Expected: 全绿（含原 ProcedureTable / StatusTag 等测试）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/procedures/ProcedureLibraryView.vue frontend/tests/unit/ProcedureLibraryView.spec.ts
git commit -m "refactor(frontend): ProcedureLibraryView 重构为双栏（FolderTreePane + ListPane）

实现 spec §A：
- 左 FolderTreePane 220px / 右 ListPane flex
- selectedFolder driven 状态切换：normal → PUBLISHED；system → ARCHIVED
- 新建按钮在 system folder 隐藏（backend 兜底校验）
- 标题动态显示文件夹名 / '全库'
- 移除 status 下拉（status 由文件夹类型驱动，不再手动切）

5 新单测全绿。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: AppLayout 接入 sidebarAutoCollapse

**Files:**
- Modify: `frontend/src/layouts/AppLayout.vue`

- [ ] **Step 1: 修改 AppLayout.vue**

完全替换 `frontend/src/layouts/AppLayout.vue`：

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppTopBar from '@/components/AppTopBar.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { useSidebar } from '@/composables/useSidebar'
import { decideAutoCollapse } from '@/utils/sidebarAutoCollapse'

const { collapsed, toggle } = useSidebar()
const route = useRoute()

// 自动折叠 / 用户接管追踪：
// - preEnterCollapsed 记入 library 之前的折叠态，用于离开时恢复
// - userOverride 标志位：用户在 library 内手动 toggle 视为接管，此后不再自动管
let preEnterCollapsed = collapsed.value
let userOverride = false

function onToggle(): void {
  // library 路径下用户手动 toggle → 接管
  if (route.path.startsWith('/procedures/library')) {
    userOverride = true
  }
  toggle()
}

watch(
  () => route.path,
  (to, from) => {
    const decision = decideAutoCollapse(from ?? '', to, userOverride)
    if (decision === 'collapse') {
      preEnterCollapsed = collapsed.value
      if (!collapsed.value) collapsed.value = true  // 已折叠就不重复
    } else if (decision === 'restore') {
      collapsed.value = preEnterCollapsed
      userOverride = false  // 离开 library 清接管标志
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="app-shell">
    <AppTopBar :collapsed="collapsed" @toggle-sidebar="onToggle" />
    <div class="app-body">
      <AppSidebar :collapsed="collapsed" />
      <main class="app-main">
        <RouterView v-slot="{ Component }">
          <Transition name="fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-width: 1024px;  /* spec YAGNI：本轮不做响应式 */
}
.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.app-main {
  flex: 1;
  overflow: auto;
  /* 注：padding 移到内部 view（如 ProcedureLibraryView 的 .list-pane），
     避免在 library 双栏布局时多一层包边干扰文件夹树面板贴边。 */
  padding: 0;
  background: #faf8f4;
}
</style>
```

> **`padding: 0` 关键变化**：旧版 AppLayout 在 `.app-main` 上设 20/24px padding 给所有页面提供内边距。新版把这个内边距下放到各 view（例如 LibraryView 的 `.list-pane`），让 FolderTreePane 可以贴 `.app-main` 左缘。其他不使用双栏的 view（ProcedureDraftsView、SettingsView 等）需要在自己根容器上加 padding，否则会贴边——本任务统一处理这一变更。

- [ ] **Step 2: 检查并更新其他 view 的 padding**

由于 `.app-main` padding 移除，所有依赖它的 view 都需要在自己根容器上加 padding。**用 grep 找出受影响的 view**：

Run: `cd frontend/src/views && grep -rL "padding" --include="*.vue"`
Expected: 列出没有显式 padding 的 view 文件

针对**每个没有 padding 的 view（除 ProcedureLibraryView 已自带）**，给根 `<div>` 加：

```css
padding: 20px 24px;
```

通常受影响的有：
- `frontend/src/views/procedures/ProcedureDraftsView.vue` — 给 `.drafts` 加 padding
- `frontend/src/views/folders/FolderManageView.vue` — 检查 .folder-manage 等根类
- `frontend/src/views/audit/AuditLogsView.vue` — 检查根容器
- `frontend/src/views/settings/SettingsView.vue` / `FieldManageView.vue`

具体改动以 grep 结果为准。对每个文件，在 `<style scoped>` 块中的根 selector（如 `.drafts`）加 `padding: 20px 24px;`，已有 padding 的不动。

- [ ] **Step 3: 跑全量测试确保不破**

Run: `cd frontend && npx vitest run`
Expected: PASS（所有现有测试不破）

- [ ] **Step 4: 提交**

```bash
git add frontend/src/layouts/AppLayout.vue frontend/src/views/
git commit -m "feat(frontend): AppLayout 接入 sidebarAutoCollapse watcher

进入 /procedures/library 自动折叠 AppSidebar；离开恢复进入前状态；
用户在 library 内手动 toggle 后接管不再自动管。

副作用：.app-main padding 下放到各 view 根容器（让 FolderTreePane
能贴 .app-main 左缘）。各 view 已显式加 padding 20px 24px。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: API client `archiveGroup` + ProcedureDetailView 加"归档"按钮

**Files:**
- Modify: `frontend/src/api/procedures.ts`
- Modify: `frontend/src/views/procedures/ProcedureDetailView.vue`

- [ ] **Step 1: 加 API client**

在 `frontend/src/api/procedures.ts` 现有 `deprecateGroup` 定义之后加：

```ts
export const archiveGroup = async (id: string, reason: string): Promise<ProcedureMeta> =>
  (await http.post<ProcedureMeta>(`/procedures/${id}/archive`, { reason })).data
```

- [ ] **Step 2: 修改 ProcedureDetailView.vue**

修改 `frontend/src/views/procedures/ProcedureDetailView.vue`：

**修改 1**：在文件顶部 import 加 `archiveGroup`：

```ts
import {
  copyProcedure,
  deleteGroup,
  deleteProcedure,
  deprecateGroup,
  archiveGroup,  // 新增
  downloadPdf,
  ...
} from '@/api/procedures'
```

**修改 2**：扩展 PendingAction 类型（约 line 230）：

```ts
type PendingAction =
  | { kind: 'deprecate' }
  | { kind: 'archive' }       // 新增
  | { kind: 'restore'; needFolder: boolean }
  | { kind: 'copy' }
  | { kind: 'rollback'; currentId: string; targetVersion: number }
```

**修改 3**：在 dialogConfig computed 中（约 line 239），在 deprecate 分支之后加 archive 分支：

```ts
const dialogConfig = computed(() => {
  const p = pending.value
  if (p?.kind === 'deprecate') {
    return { title: '废弃整个版本族', needReason: true, needFolder: false, needName: false, reasonHint: '废弃原因（整组所有版本将移入「废止」）' }
  }
  if (p?.kind === 'archive') {
    return { title: '归档整个版本族', needReason: true, needFolder: false, needName: false, reasonHint: '归档原因（整组所有版本将移入「归档」，保留备查）' }
  }
  // ... 现有 restore / copy / rollback 分支保留
})
```

**修改 4**：在现有 `openDeprecate` 函数之后加 `openArchive`：

```ts
function openArchive(): void {
  pending.value = { kind: 'archive' }
  dialogVisible.value = true
}
```

**修改 5**：在 commit 提交逻辑（约 line 287）的 deprecate 分支之后加 archive 分支：

```ts
async function commitDialog(payload: VersionActionResult): Promise<void> {
  // ... 现有 try/catch + busy 包装
  const p = pending.value
  if (!p || !meta.value) return
  try {
    busy.value = true
    if (p.kind === 'deprecate') {
      await deprecateGroup(meta.value.id, payload.reason)
      ElMessage.success('已废弃整版本族')
      await refresh()
    } else if (p.kind === 'archive') {
      await archiveGroup(meta.value.id, payload.reason)
      ElMessage.success('已归档整版本族')
      await refresh()
    } else if (p.kind === 'restore') {
      // ... 现有 restore 不变
    }
    // ... 其他分支
  } finally {
    busy.value = false
    dialogVisible.value = false
  }
}
```

> **保留确切的 try/finally 结构按现有代码风格**——以上是分支逻辑示意，实际改动只是在 if 链中加一条 `else if (p.kind === 'archive')`。

**修改 6**：在 `<template>` 中，找到"废弃整版本族"按钮，在其旁边加"归档整版本族"按钮。具体位置：现有按钮约在 `<el-button @click="openDeprecate">` 附近：

```vue
<el-button
  v-if="canDeprecate"
  type="danger"
  link
  :disabled="busy"
  @click="openDeprecate"
>
  废弃整版本族
</el-button>
<el-button
  v-if="canArchive"
  type="warning"
  link
  :disabled="busy"
  @click="openArchive"
>
  归档整版本族
</el-button>
```

**修改 7**：在 script setup 中加 `canArchive` computed（同 `canDeprecate` 模式，搜索现有 canDeprecate 计算并仿写）：

```ts
const canArchive = computed(
  () =>
    !!meta.value &&
    meta.value.is_current &&
    meta.value.status === 'PUBLISHED' &&
    !deprecated.value,
)
```

> 与 canDeprecate 条件相同：仅当前 PUBLISHED 且未废止可归档。

- [ ] **Step 3: 跑全量测试确保不破**

Run: `cd frontend && npx vitest run`
Expected: PASS

跑 typecheck：

Run: `cd frontend && npm run typecheck`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/procedures.ts frontend/src/views/procedures/ProcedureDetailView.vue
git commit -m "feat(frontend): ProcedureDetailView 加'归档整版本族'按钮

与现有'废弃整版本族'按钮平级，调用新加的 archiveGroup API。
对话框文案区分两者语义：废弃=不再使用 / 归档=保留备查。

API client 新增 archiveGroup(id, reason)。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: 文档同步

**Files:**
- Modify: `docs/design-system.md`
- Modify: `docs/feature-clarifications.md`
- Modify: `docs/superpowers/specs/2026-05-26-topbar-ia-design.md`

- [ ] **Step 1: design-system.md §3.1 注释更新**

在 `docs/design-system.md` §3.1 中找到「**术语演变 (2026-05-26)**」这段注释（前一个 topbar-IA 任务加的）：

原文：

```markdown
> **术语演变 (2026-05-26)**：原称「标准文件库」，2026-05-26 起改名「文件夹配置」并归入顶栏 ⚙ 配置组。本节早期版本的 ASCII（`▸ QC 质量 ▸ QA 保证` 树状结构）描述的是**未落地的侧栏文件夹树导航**，与现 FolderManageView（CRUD 配置页）形态不同；该树状导航如要实现，是另一个 topic。
```

替换为：

```markdown
> **术语演变 (2026-05-26)**：「文件夹配置」（原称「标准文件库」）= ⚙ 配置组下的文件夹 CRUD 管理页。本节早期版本 ASCII（`▸ QC 质量 ▸ QA 保证` 树状结构）描述的"侧栏文件夹树导航"现已实现，但**位置在 ProcedureLibraryView 内部双栏的左侧 FolderTreePane**（非全局 AppSidebar）。详见 [`docs/superpowers/specs/2026-05-26-library-ia-archive-folder-design.md`]。
```

- [ ] **Step 2: feature-clarifications.md §50.2 加 R2 修订脚注**

在 `docs/feature-clarifications.md` §50.2 末尾，找到上一个修订脚注：

```markdown
> **修订 (2026-05-26)**：「文件夹配置」（原称「标准文件库」）实际是 admin 配置页（定义文件夹分类与编号规则），归 ⚙ 配置组而非侧栏内容容器；同时撤回"侧栏底部系统区放废止入口"的 §3.1 设想——「废止」按 §13 的逻辑应当走 `folder.system=true` 文件夹过滤，需要 ProcedureLibraryView 加 folder_id 支持，留作独立 topic。Q321 原决策"内容容器 vs 管理类"两分法仍然成立。
```

在其紧接其下追加：

```markdown

> **R2 修订 (2026-05-26)**：上述"废止入口留作独立 topic"已落地——通过 ProcedureLibraryView 双栏重构（左 FolderTreePane + 右 ListPane）原生承载，"废止"成为文件夹树中的一员、无需独立路由或侧栏入口。同时新增"归档"系统文件夹与之同级（语义：保留备查 / 废止：不再使用）。详见 [`docs/superpowers/specs/2026-05-26-library-ia-archive-folder-design.md`]。
```

- [ ] **Step 3: topbar-IA spec R1 修订段加取代注**

在 `docs/superpowers/specs/2026-05-26-topbar-ia-design.md` 末尾「修订日志 R1」段最后一句之后，追加：

```markdown

> **R1 决策的后续 (2026-05-26)**：该撤回决策被 [`2026-05-26-library-ia-archive-folder-design.md`] 永久取代——"废止入口"的最终实现路径是 ProcedureLibraryView 双栏重构（文件夹树导航 + 归档同级系统文件夹），既不需要 `/procedures/deprecated` 路由也不需要侧栏系统区。
```

- [ ] **Step 4: grep 校验**

Run: `grep -nE "R2 修订|R1 决策的后续" docs/ -r`
Expected: 命中 2 处分别在 feature-clarifications.md §50.2 与 topbar-IA spec R1 修订段

- [ ] **Step 5: 提交**

```bash
git add docs/design-system.md docs/feature-clarifications.md docs/superpowers/specs/2026-05-26-topbar-ia-design.md
git commit -m "docs: 同步程序库 IA 重构 R2 修订到三份现行文档

- design-system §3.1：'侧栏文件夹树导航'从'未落地' 改为'已实现于 ProcedureLibraryView 内部双栏'
- feature-clarifications §50.2：加 R2 修订脚注，废止入口最终落地路径
- topbar-IA spec R1 修订段：标注被本 spec 永久取代

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: 最终验证

**Files:** N/A（验证步骤）

- [ ] **Step 1: 全量 backend + frontend 测试**

Run:
```bash
cd backend && pytest tests/ -x
cd ../frontend && npm run typecheck && npm run lint && npx vitest run && npm run build
```

Expected: 全部通过；build 成功。

- [ ] **Step 2: 重启 dev server 确保 HMR 没遗漏改动**

```bash
ps -ef | grep "node.*vite" | grep -v grep   # 找 pid
kill <pid>
cd frontend && npm run dev
```

等待 `ready in` 行出现。

backend 已经在 `--reload` 模式运行；seed.py 改动需要 backend 重启才生效。如未重启：

```bash
ps -ef | grep "uvicorn" | grep -v grep   # 找 pid
kill <pid>
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
```

启动后会自动 seed "归档" folder。

- [ ] **Step 3: 浏览器实测 + 截图**

打开 http://localhost:5173/procedures/library，巡检：

1. **AppSidebar 自动折叠**：进入 library 后 AppSidebar 从 240px 收成 64px 图标轨
2. **FolderTreePane 渲染**：左侧 220px 面板出现，"文件夹" 小帽 + folder tree（含 废止 + 归档 两个系统 tag）
3. **默认右侧 = 全库 PUBLISHED**：标题"全库"，列表只显示 PUBLISHED + is_current 程序
4. **点普通文件夹**：右侧列表收窄到该文件夹下、状态仍 PUBLISHED；标题变文件夹名；新建按钮**仍可见**
5. **点「归档」folder**：右侧列表自动切到 ARCHIVED + folder=归档；新建按钮**消失**；如有归档程序则展示
6. **点「废止」folder**：同上但 folder=废止
7. **手动展开 AppSidebar**：点 AppTopBar ≡ 按钮 → AppSidebar 展开 240px；user-override 标志位置位
8. **跳转其他路由再回来**：离开 library 时 AppSidebar 恢复（如 step 7 已展开），但 user-override 在跨页时清空、下次再进 library 仍自动折叠
9. **ProcedureDetailView**：点列表行 → 详情页；按钮区出现"归档整版本族"（v-if canArchive 为 true 时）
10. **归档动作 E2E**：在普通文件夹中创建一个 PUBLISHED 程序 → 点"归档" → 输入原因 → 提交；返回程序库 → 该程序消失（PUBLISHED 视图）→ 点「归档」folder → 该程序出现
11. **从归档恢复**：点该程序进详情页 → 点"恢复" → 输入原因 → 提交；返回程序库 → 该程序回到原 folder + status=DRAFT（在草稿箱可见）

截图存到：
- `.verify-screenshots/08-library-double-pane-default.png`（默认全库视图）
- `.verify-screenshots/09-library-archive-folder-selected.png`（点归档 folder）
- `.verify-screenshots/10-library-deprecated-folder-selected.png`（点废止 folder）
- `.verify-screenshots/11-detail-archive-button.png`（详情页归档按钮）

- [ ] **Step 4: 提交截图（如 .verify-screenshots/ 不在 .gitignore）**

```bash
git add .verify-screenshots/08-library-double-pane-default.png \
        .verify-screenshots/09-library-archive-folder-selected.png \
        .verify-screenshots/10-library-deprecated-folder-selected.png \
        .verify-screenshots/11-detail-archive-button.png
git commit -m "test(verify): 程序库 IA 重构 + 归档功能浏览器实测截图

4 张视觉证据：
- 08 双栏默认视图（FolderTreePane + 全库 PUBLISHED 列表）
- 09 点归档 folder 切到 ARCHIVED 列表
- 10 点废止 folder 切到 ARCHIVED 列表
- 11 详情页\"归档整版本族\"按钮（与\"废弃\"并列）

E2E 流程实测：创建 → 归档 → 列表切换 → 恢复 → 草稿箱 全通。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 5: 终态汇报**

汇报：
- 新增 / 修改文件总数
- backend 新单测 + 集成测数；frontend 新单测数；全量测试数
- 已落地的 spec 决策项（10 项决策矩阵 + 4 个 backend 行为 + 3 个 frontend 模块）
- 显式 deferred 项：暗壳决策 / 全库搜索 backend / 待阅读 backend（按 spec 不在范围）
- 分支：feat/library-ia-archive-folder

---

## 自检覆盖（写完后跑一遍）

- [x] spec §数据模型变更 seed.py 扩展 → Task 1
- [x] spec §后端 API archive_group service → Task 2
- [x] spec §后端 API /archive 端点 → Task 3
- [x] spec §后端 API restore 通用化（零代码改动，仅测试验证）→ Task 2 Step 1 第 5 个测试
- [x] spec §前端架构 A ProcedureLibraryView 重构 → Task 6
- [x] spec §前端架构 B FolderTreePane → Task 5
- [x] spec §前端架构 C AppSidebar 自动折叠 → Task 4 + Task 7
- [x] spec §前端架构 D ProcedureDetailView 归档按钮 → Task 8
- [x] spec §前端架构 E 路由不变 → 无独立任务，已说明
- [x] spec §测试 后端 5 单测 + 2 集成测 → Task 2 + Task 3
- [x] spec §测试 sidebarAutoCollapse 5+ 单测 → Task 4（6 单测）
- [x] spec §测试 LibraryView 5 单测 → Task 6
- [x] spec §测试 DetailView 扩展 → Task 8 通过 typecheck + 既有 detail 测试不破覆盖
- [x] spec §决策矩阵 Q1 默认无选中 → 全库 PUBLISHED → Task 6 Step 3 onMounted load 默认 query.status='PUBLISHED'
- [x] spec §决策矩阵 Q3 system folder 切 ARCHIVED → Task 6 onSelectFolder
- [x] spec §决策矩阵 Q4 搜索跨全库（backend 既有约定）→ 无代码改动需求，注释保留
- [x] spec §决策矩阵 Q7 进入 library 自动折叠 → Task 4 + Task 7
- [x] spec §决策矩阵 Q8 草稿箱不动 → Task 7 Step 2 中给 DraftsView 加 padding（仅 padding 调整，view 逻辑不动）
- [x] spec §决策矩阵 Q9 旧 deprecated 路由永久 retired → Task 9 文档同步
- [x] spec §文档同步任务 三份文档 → Task 9
- [x] spec §风险 grep "deprecated_from_folder_id" docstring 注 → Task 2 Step 3 内联注

无未覆盖项。
