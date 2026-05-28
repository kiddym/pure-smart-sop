# 统一节点模型 B3b-2 — 删除旧结构编辑器 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除 B3b-1 切换后休眠的旧结构编辑代码——旧章节/内容/步骤树 + 详情面板 + 退役的 NodeEditorView 壳 + layerMark + 标记/层级/转换/批量保存/撤销逻辑（收窄 `procedureEditor` 为元数据 store）+ 死 api 导出 + 废测试，并删 `batchMark` 的 chapter-skip。app 行为不变（已全程跑统一节点编辑器）。

**Architecture:** 纯删除 + 收窄。这是 **B4 之前的 contract 化前置**：把 B3b-1 已不再调用的旧代码物理删除。**删除型任务的「测试」= 删后全量 vitest 仍绿 + `vue-tsc --noEmit` 干净（兜悬挂引用）+ grep 确认无残留引用**（非 red-green TDD）。按依赖序删（先删叶子消费者，再删被依赖者），每次 commit 保持可编译。

**Tech Stack:** Vue 3 + Pinia + TypeScript + vitest。前端测试 `cd frontend && npx vitest run`；类型 `npx vue-tsc --noEmit`；lint `npx eslint <files> --max-warnings 0`。

**Spec:** `docs/superpowers/specs/2026-05-28-unified-node-model-b3b-switch-delete-design.md`（§删除清单）。**Prep（含 store↔store 重名陷阱 + 确认安全删清单）：** 记忆 `b3b2-deletion-prep`。

**前置事实（B3b-1 已合并 `8310f4e`）：** `ProcedureEditorView` 已默认渲染 `NodeTreePanel`+`NodeDetailPanel`（绑 `nodeEditor`），不再 import 旧组件/composables/结构 store 成员；`procedureEditor.setMetaField` 已即时存。`procedureEditor` 与 `nodeEditor` **成员重名**（`selectedId`/`undo`/`redo`/`selection`/`load`），grep consumer 时务必区分 store——`procedureEditor` 的结构成员已无 live 消费者。

---

## procedureEditor.ts 现状 keep/delete 分类（实测 main，1110 行）

**KEEP**：import `defineStore`、`fetchProcedureDetail`/`updateProcedure`、type `ProcedureFieldView`/`ProcedureMeta`/`ProcedureUpdate`；常量 `META_FLUSH_MS`(:44) + `metaFlushTimer`(:45)；state `procedure`/`hasSourceDocx`/`fields`/`loading`/`loadError`；getter `editable`(:188)/`revision`(:200)；action `load`(:377,收窄)/`reload`(:729,收窄)/`setMetaField`(:958)/`_scheduleMetaFlush`(:964)/`_flushMeta`(:971)。
**DELETE**：import `saveProcedure`/`applyMarks`/`applyLayerRolesApi`、整个 `@/api/chapters`、`@/api/steps`、`@/utils/editor`、`@/utils/layerMark` import、`@/types/node` import 整块、`ProcedureSaveIn`；常量 `MAX_UNDO`/`COALESCE_MS`/`CONTENT_MAX_BYTES`；helper `byteLength`/`Snapshot`/`clone`/`emptyStep`/`ingestChapters`/`ingestStep`/`patchChangesAnything`；类型 `EditorDraftState`；state `chapters`/`steps`/`selectedId`/`expanded`/`dirtyChapters`/`dirtySteps`/`deletedChapterIds`/`deletedStepIds`/`metaDirty`/`markMode`/`layerMode`/`saving`/`undoStack`/`redoStack`/`lastUndoTag`/`lastUndoAt`/`inflightSplit`；getter `isDirty`/`chapterMap`/`stepMap`/`codeMaps`/`levelMap`/`layerRows`/`childKindsOf`/`addButtonStateFor`/`missingTitleCount`/`chapterDocRows`/`selectedChapter`/`selectedStep`/`markedNodes`/`flatRows`；action 其余全部（resetEditState/firstNodeId/expandAll/selectNode/setExpanded/toggleExpanded/expandAncestors/pushUndo/snapshot/restore/undo/redo/updateChapterFields/updateStepFields/setStepFormType/toggleSkipNumbering/nextSortOrder/addChapterNode/addStepNode/setStepKind/reorder/swapInGroup/reorderWithin/removeNodeLocal/collectSubtree/deleteNode/ensureSaved/convertToStep/convertRootToStep/convertToChapter/refreshAfterConversion/convertChapterToContent/splitChapterTitleContent/moveCrossParent/resequenceChapterGroup/resequenceChapterGroupWithInsert/resequenceStepGroup/resequenceStepGroupWithInsert/toggleMarkMode/toggleLayerMode/applyLayerRoles/setMark/acceptReview/acceptAllReviews/cycleMark/applyAllMarks/exportDraft/importDraft/validateForSave/buildPayload/applyIdMap/save）。

---

## 文件结构

| 文件 | 动作 |
|---|---|
| `src/components/editor/ChapterTreePanel.vue` / `TreeRow.vue` / `ChapterDetailPanel.vue` / `ContentDetailPanel.vue` / `StepDetailPanel.vue` | 删除 |
| `src/views/procedures/NodeEditorView.vue` | 删除（B3a-2 壳，B3b-1 去 gate 后无引用） |
| `src/composables/useEditorPersistence.ts` / `useEditorKeyboard.ts` | 删除（B3b-1 后无 import） |
| `src/store/procedureEditor.ts` | 收窄为元数据 store（verbatim 替换，~75 行） |
| `src/utils/layerMark.ts` | 删除 |
| `src/api/procedures.ts` | 删死导出 `saveProcedure`/`applyMarks`/`applyLayerRolesApi` + 其 type import |
| `src/api/chapters.ts` / `src/api/steps.ts` | 删 grep 确认无消费者的 convert*/setChapterMarkStatus（视情况） |
| `src/utils/batchMark.ts` | 删 `kind === 'chapter'` skip |
| `tests/unit/...` | 删整文件废测试 + 替换 store spec + 裁剪 batchMark spec |

---

## Task 1: 删除孤立旧组件 + composables + 整文件废测试

**Files:**
- Delete: `src/components/editor/ChapterTreePanel.vue`, `src/components/editor/TreeRow.vue`, `src/components/editor/ChapterDetailPanel.vue`, `src/components/editor/ContentDetailPanel.vue`, `src/components/editor/StepDetailPanel.vue`, `src/views/procedures/NodeEditorView.vue`, `src/composables/useEditorPersistence.ts`, `src/composables/useEditorKeyboard.ts`
- Delete tests: `tests/unit/ChapterTreePanel.spec.ts`, `tests/unit/TreeRow.spec.ts`, `tests/unit/ChapterDetailPanel.spec.ts`, `tests/unit/ContentDetailPanel.spec.ts`, `tests/unit/NodeEditorView.spec.ts`（+ 若存在 `useEditorPersistence`/`useEditorKeyboard` 的 spec）

- [ ] **Step 1: 删前确认无 live importer（安全门）**

Run（每个被删源文件 grep 其 import，期望仅命中将一并删除的文件或零）：
```
cd frontend
for f in ChapterTreePanel TreeRow ChapterDetailPanel ContentDetailPanel StepDetailPanel; do echo "== $f =="; grep -rn "editor/$f'" src/ --include=*.vue --include=*.ts | grep -v "components/editor/$f.vue"; done
echo "== NodeEditorView =="; grep -rn "NodeEditorView" src/
echo "== useEditorPersistence =="; grep -rn "useEditorPersistence" src/
echo "== useEditorKeyboard =="; grep -rn "useEditorKeyboard" src/
```
Expected: 所有 grep 为空（无 live importer）。`ChapterTreePanel` 的命中应仅在 `ChapterTreePanel.vue` 自身（已被 grep -v 排除）→ 空。**若任何 grep 返回一个非被删文件的 import，STOP 并报告**（说明还有 live 消费者，需先处理）。

- [ ] **Step 2: 删除源文件 + 测试文件**

```
cd frontend
git rm src/components/editor/ChapterTreePanel.vue src/components/editor/TreeRow.vue src/components/editor/ChapterDetailPanel.vue src/components/editor/ContentDetailPanel.vue src/components/editor/StepDetailPanel.vue src/views/procedures/NodeEditorView.vue src/composables/useEditorPersistence.ts src/composables/useEditorKeyboard.ts
git rm tests/unit/ChapterTreePanel.spec.ts tests/unit/TreeRow.spec.ts tests/unit/ChapterDetailPanel.spec.ts tests/unit/ContentDetailPanel.spec.ts tests/unit/NodeEditorView.spec.ts
```
然后 `ls tests/unit/composables/ 2>/dev/null` 与 `grep -rln "useEditorPersistence\|useEditorKeyboard" tests/`：若存在对应 spec，一并 `git rm`。

- [ ] **Step 3: 验证 tsc + 全量 vitest 绿**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 干净（删的都是孤立文件 → 无悬挂）。

Run: `cd frontend && npx vitest run`
Expected: 全绿（少了被删文件的用例；1 个先存 `ChapterDetailPanel` offsetHeight unhandled rejection **应随 ChapterDetailPanel.spec 删除而消失**——即 0 errors 或仅剩其它已知项）。记录 Test Files / Tests 数。

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(fe): delete orphaned legacy editor components + composables + their specs (B3b-2)"
```

---

## Task 2: 收窄 `procedureEditor` 为元数据 store + 替换/删废 store 测试

**Files:**
- Modify (verbatim replace): `src/store/procedureEditor.ts`
- Delete: `tests/unit/store/procedureEditor.applyLayerRoles.spec.ts`
- Replace: `tests/unit/store/procedureEditorStore.spec.ts` → 新建聚焦 `tests/unit/store/procedureEditor.spec.ts`（删旧大文件、建小文件）
- Keep (不动)：`tests/unit/store/procedureEditor.metaImmediate.spec.ts`（B3b-1 的 setMetaField 即时存测试；其 `vi.mock('@/api/procedures')` 工厂里多余的 `saveProcedure`/`applyMarks`/`applyLayerRolesApi` key 无害）

- [ ] **Step 1: verbatim 替换 `src/store/procedureEditor.ts` 全文为：**

```typescript
// 编辑器程序级元数据 store（B3b-2 起收窄：结构编辑全部迁至 nodeEditor）。
// 即时·乐观写：setMetaField 改本地 + 防抖 updateProcedure。批量保存/撤销/层级/标记/转换/树结构已删。

import { defineStore } from 'pinia'
import { fetchProcedureDetail, updateProcedure } from '@/api/procedures'
import type { ProcedureFieldView, ProcedureMeta, ProcedureUpdate } from '@/types/procedure'

const META_FLUSH_MS = 500
let metaFlushTimer: ReturnType<typeof setTimeout> | null = null

interface State {
  procedure: ProcedureMeta | null
  hasSourceDocx: boolean
  fields: ProcedureFieldView[]
  loading: boolean
  loadError: boolean
}

export const useProcedureEditorStore = defineStore('procedureEditor', {
  state: (): State => ({
    procedure: null,
    hasSourceDocx: false,
    fields: [],
    loading: false,
    loadError: false,
  }),

  getters: {
    editable(state): boolean {
      return !!state.procedure && state.procedure.is_current && state.procedure.status === 'DRAFT'
    },
    revision(state): number {
      return state.procedure?.revision ?? 0
    },
  },

  actions: {
    async load(id: string): Promise<void> {
      this.loading = true
      this.loadError = false
      try {
        const detail = await fetchProcedureDetail(id)
        this.procedure = detail.procedure
        this.hasSourceDocx = detail.has_source_docx
        this.fields = detail.fields
      } catch {
        this.loadError = true
      } finally {
        this.loading = false
      }
    },

    async reload(): Promise<void> {
      if (this.procedure) await this.load(this.procedure.id)
    },

    // 程序级元字段编辑（详情折叠面板）。即时·乐观写：本地先改 + 防抖 flush。
    setMetaField<K extends keyof ProcedureMeta>(key: K, value: ProcedureMeta[K]): void {
      if (!this.procedure) return
      this.procedure[key] = value
      this._scheduleMetaFlush()
    },

    _scheduleMetaFlush(): void {
      if (metaFlushTimer) clearTimeout(metaFlushTimer)
      metaFlushTimer = setTimeout(() => {
        void this._flushMeta()
      }, META_FLUSH_MS)
    },

    async _flushMeta(): Promise<void> {
      metaFlushTimer = null
      const p = this.procedure
      if (!p || !this.editable) return
      const payload: ProcedureUpdate = {
        name: p.name,
        level_of_use: p.level_of_use,
        description: p.description,
        risk_level: p.risk_level,
        quality_level: p.quality_level,
        custom_values: p.custom_values,
        version_update_notes: p.version_update_notes,
        signoff_enabled: p.signoff_enabled,
      }
      try {
        const updated = await updateProcedure(p.id, payload, p.revision)
        // 只同步 revision，避免冲掉 flush 期间的并发本地编辑。
        if (this.procedure && this.procedure.id === updated.id) this.procedure.revision = updated.revision
      } catch {
        await this.reload()
      }
    },
  },
})
```

- [ ] **Step 2: 删废 store 测试 + 建聚焦 spec**

```
cd frontend
git rm tests/unit/store/procedureEditor.applyLayerRoles.spec.ts
git rm tests/unit/store/procedureEditorStore.spec.ts
```
Create `tests/unit/store/procedureEditor.spec.ts`（聚焦收窄后的 store：load 成功/失败、editable、reload；setMetaField 即时存由 `procedureEditor.metaImmediate.spec.ts` 覆盖）：

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { ProcedureMeta } from '@/types/procedure'

const { detailSpy } = vi.hoisted(() => ({ detailSpy: vi.fn() }))
vi.mock('@/api/procedures', () => ({
  fetchProcedureDetail: detailSpy,
  updateProcedure: vi.fn(),
}))

import { useProcedureEditorStore } from '@/store/procedureEditor'

function meta(over: Partial<ProcedureMeta> = {}): ProcedureMeta {
  return {
    id: 'p1', code: 'C-1', name: 'N', level_of_use: 'reference',
    description: '', risk_level: 1, quality_level: 1, custom_values: {},
    version_update_notes: '', signoff_enabled: false,
    revision: 1, version: 1, status: 'DRAFT', is_current: true,
    version_change_log: [],
    ...over,
  } as unknown as ProcedureMeta
}

beforeEach(() => {
  setActivePinia(createPinia())
  detailSpy.mockReset()
})

describe('procedureEditor (slim meta store, B3b-2)', () => {
  it('load() populates procedure/hasSourceDocx/fields from detail', async () => {
    detailSpy.mockResolvedValue({ procedure: meta(), has_source_docx: true, fields: [{ id: 'f1' }] })
    const store = useProcedureEditorStore()
    await store.load('p1')
    expect(store.procedure?.id).toBe('p1')
    expect(store.hasSourceDocx).toBe(true)
    expect(store.fields).toHaveLength(1)
    expect(store.loadError).toBe(false)
  })

  it('load() sets loadError on failure', async () => {
    detailSpy.mockRejectedValue(new Error('boom'))
    const store = useProcedureEditorStore()
    await store.load('p1')
    expect(store.loadError).toBe(true)
    expect(store.procedure).toBeNull()
  })

  it('editable is true only for current DRAFT', async () => {
    const store = useProcedureEditorStore()
    store.procedure = meta({ status: 'DRAFT', is_current: true })
    expect(store.editable).toBe(true)
    store.procedure = meta({ status: 'PUBLISHED', is_current: true })
    expect(store.editable).toBe(false)
    store.procedure = meta({ status: 'DRAFT', is_current: false })
    expect(store.editable).toBe(false)
  })

  it('reload() re-fetches the current procedure', async () => {
    detailSpy.mockResolvedValue({ procedure: meta({ name: 'fresh' }), has_source_docx: false, fields: [] })
    const store = useProcedureEditorStore()
    store.procedure = meta({ name: 'stale' })
    await store.reload()
    expect(detailSpy).toHaveBeenCalledWith('p1')
    expect(store.procedure?.name).toBe('fresh')
  })
})
```

- [ ] **Step 3: 验证 tsc + 全量 vitest 绿**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 干净。**注**：此步会暴露任何仍引用被删 store 成员的 live 文件（应无——B3b-1 已切干净）。若 tsc 报某 `.vue`/`.ts` 引用了 `store.isDirty`/`store.save`/`store.chapters` 等已删成员，说明有遗漏的 live 消费者——STOP 报告（不要给 store 加回成员）。

Run: `cd frontend && npx vitest run`
Expected: 全绿（含新 `procedureEditor.spec.ts` 4 + 既有 `procedureEditor.metaImmediate.spec.ts`）。

- [ ] **Step 4: Commit**

```bash
git add src/store/procedureEditor.ts tests/unit/store/procedureEditor.spec.ts
git commit -m "refactor(fe/procedureEditor): narrow to slim meta store; drop all structural/save/undo/layer/mark/convert code (B3b-2)"
```
（`git rm` 的删除已被 `git commit` 捕获；确保 `git status` 干净。）

---

## Task 3: 删孤立 `layerMark.ts` + 死 api 导出 + 其测试

**Files:**
- Delete: `src/utils/layerMark.ts`, `tests/unit/utils/layerMark.spec.ts`
- Modify: `src/api/procedures.ts`（删 `saveProcedure`/`applyMarks`/`applyLayerRolesApi` + 其 type import）
- Modify（视 grep）: `src/api/chapters.ts`, `src/api/steps.ts`（删无消费者的 convert*/setChapterMarkStatus）

- [ ] **Step 1: 确认 layerMark 已无 importer（Task 2 后）**

Run: `cd frontend && grep -rn "utils/layerMark" src/`
Expected: 空（Task 2 narrow 已删 procedureEditor 的 import；旧组件 Task 1 已删）。若非空，STOP 报告。

- [ ] **Step 2: 删 layerMark + spec**

```
cd frontend && git rm src/utils/layerMark.ts tests/unit/utils/layerMark.spec.ts
```

- [ ] **Step 3: 删 api 死导出**

In `src/api/procedures.ts`：删除 `saveProcedure`、`applyMarks`、`applyLayerRolesApi` 三个导出函数定义；并从该文件顶部 import 删除仅它们用到的类型 `ApplyMarksResult`、`LayerApplyIn`、`LayerApplyResult`（保留 `ProcedureSaveIn`?——见下）。先确认无消费者：
```
cd frontend && for fn in saveProcedure applyMarks applyLayerRolesApi; do echo "== $fn =="; grep -rn "\b$fn\b" src/ tests/; done
```
Expected：仅命中 `api/procedures.ts` 自身定义（+ `procedureEditor.metaImmediate.spec.ts` 的 vi.mock 工厂 key——那是 mock 对象键、非 import，**保留无害**，不必改）。删除三函数后，若 `ProcedureSaveIn` 类型在 `api/procedures.ts` 已无其它用处则一并从 import 删（grep `ProcedureSaveIn` in `src/api/procedures.ts`）。`LayerApplyIn`/`LayerApplyResult`/`ApplyMarksResult` type 定义留在 `types/node.ts`（B4 清），仅删 `api/procedures.ts` 的 import。

对 `convertChapterToStep`/`convertRootToStep`/`convertChapterToContent`/`splitChapterTitleContent`（`api/chapters.ts`）、`convertStepToChapter`（`api/steps.ts`）、`setChapterMarkStatus`（`api/chapters.ts`）：
```
cd frontend && for fn in convertChapterToStep convertRootToStep convertChapterToContent splitChapterTitleContent convertStepToChapter setChapterMarkStatus; do echo "== $fn =="; grep -rn "\b$fn\b" src/ tests/; done
```
对每个**仅命中自身定义**（无 live 消费者）的函数，从其 api 文件删除该导出。**有任何其它消费者的保留**（报告）。

- [ ] **Step 4: 验证 tsc + eslint + 全量 vitest**

Run: `cd frontend && npx vue-tsc --noEmit` → 干净。
Run: `cd frontend && npx eslint src/api/procedures.ts src/api/chapters.ts src/api/steps.ts --max-warnings 0` → 干净（无未用 import 残留）。
Run: `cd frontend && npx vitest run` → 全绿。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(fe): delete layerMark + dead api exports (save/apply-marks/apply-layer-roles + unused convert*) (B3b-2)"
```

---

## Task 4: `batchMark.ts` 删 chapter-skip + 裁剪 spec

**Files:**
- Modify: `src/utils/batchMark.ts`（删 `if (r.kind === 'chapter') continue`，约 :51；+ 任何其它 `=== 'chapter'` 分支）
- Modify: `tests/unit/utils/batchMark.spec.ts`（删依赖 chapter 行的旧用例，保留 node 行用例）

- [ ] **Step 1: 定位 + 删 chapter 分支**

Run: `cd frontend && grep -n "=== 'chapter'\|'chapter'" src/utils/batchMark.ts`
删除 `buildSelection` 内 shift-range 循环里的 `if (r.kind === 'chapter') continue`（及 `buildCascadeSelection` 内任何 chapter 专属分支，如有）。统一模型 node 的 `kind` 仅 `'node'|'step'`，该分支对 node 行恒不触发，删之收口（`SelectableRow.kind` 已是 `string`，类型不变）。

- [ ] **Step 2: 裁剪 spec**

Read `tests/unit/utils/batchMark.spec.ts`。删除**仅为验证 chapter-skip 语义**的用例（rows 里含 `kind:'chapter'` 且断言 chapter 被跳过的 `it`）。**保留** `describe('buildSelection — node rows (kind node|step)', ...)`（B3a-2 加）与任何 step/content 行为用例。若某 `it` 混用 chapter 行做一般区间断言，改其 rows 为 node 行（`'node'|'step'`）使断言仍成立；不能简单改的则删除该 chapter-专属 `it`。

- [ ] **Step 3: 验证**

Run: `cd frontend && npx vitest run tests/unit/utils/batchMark.spec.ts` → 绿。
Run: `cd frontend && npx vue-tsc --noEmit && npx eslint src/utils/batchMark.ts tests/unit/utils/batchMark.spec.ts --max-warnings 0` → 干净。

- [ ] **Step 4: Commit**

```bash
git add src/utils/batchMark.ts tests/unit/utils/batchMark.spec.ts
git commit -m "refactor(fe/batchMark): drop chapter-skip (node model has no chapter kind) (B3b-2)"
```

---

## Task 5: 全量回归 + 类型 + lint + grep 清扫 + 手动 dev 验收

**Files:** 无新增

- [ ] **Step 1: 全部前端测试**

Run: `cd frontend && npx vitest run`
Expected: 全绿。记录 Test Files / Tests 数（应明显少于 B3b-1 的 458——删了多文件 spec + 收窄 store spec）。确认 Errors 行不含新增项（先存 `ChapterDetailPanel` offsetHeight 项应已随其 spec 删除消失）。

- [ ] **Step 2: 类型 + lint（全量）**

Run: `cd frontend && npx vue-tsc --noEmit` → 干净。
Run: `cd frontend && npx eslint . --ext .ts,.vue --max-warnings 0`（或项目既有 lint 脚本 `npm run lint`）→ 干净（无未用 import / 悬挂引用）。

- [ ] **Step 3: grep 清扫——确认无残留引用**

Run（期望全空）：
```
cd frontend && grep -rn "ChapterTreePanel\|ChapterDetailPanel\|ContentDetailPanel\|StepDetailPanel\|NodeEditorView\|layerMark\|useEditorPersistence\|useEditorKeyboard\|\.applyLayerRoles\|\.buildPayload\|\.applyAllMarks\|store\.save\b\|\.isDirty\b" src/
```
任何命中都要核：若是被删符号的残留引用 → 处理；若是 `nodeEditor` 的同名成员（如 `.undo`）→ 忽略（重名陷阱，见 [[b3b2-deletion-prep]]）。`grep "'chapter'" src/utils/batchMark.ts` 应为空。

- [ ] **Step 4: 手动 dev 验收（running-smartsop-dev + chrome-devtools）**

启动 dev（见 `running-smartsop-dev`；worktree 跑前端需 symlink `frontend/node_modules`）。
- **/edit（草稿）**：默认渲染统一编辑器；节点树 chip/新增/删除/拖拽、详情 body/step 表单、撤销、autosave、**程序详情改字段即时落库**均正常（功能与 B3b-1 一致，仅删了死代码）。
- **/view（已发布版）**：只读正常（无编辑能力、只读 banner）。
- dev.db 现有程序多 0 node（空树非 bug，见 [[unified-node-model-direction]]）；可在 /edit 新增节点验证。
- 截图存 `.verify-screenshots/`（该目录**含历史已跟踪截图，勿 `rm -rf`**）。

- [ ] **Step 5: Commit（若有修正）**

```bash
git add -A
git commit -m "chore(fe): grep-sweep/lint fixes for B3b-2"
```

---

## 执行须知（worktree）
- 前端 worktree 需 bootstrap `frontend/node_modules`（symlink 父 repo）。`.verify-screenshots/` 已跟踪，勿删。
- 子代理从 worktree 派发默认 cwd 是父 repo——命令用绝对 worktree 路径，commit 后验 `git rev-parse --abbrev-ref HEAD` = 本次分支名。
- 基线（合并前 main `8310f4e`）：前端 458 passed + 1 先存 `ChapterDetailPanel` offsetHeight error（本期删 ChapterDetailPanel.spec 后该 error 应消失）。

## 完成标准（B3b-2）
1. 旧组件/`NodeEditorView`/composables/`layerMark`/死 api 导出/废测试 物理删除；`procedureEditor` 收窄为元数据 store。
2. `batchMark` 去 chapter-skip。
3. 全 vitest 绿、`vue-tsc`/eslint 全量干净、grep 清扫无残留旧引用；`/edit`+`/view` 手动验收功能与 B3b-1 一致；后端不受影响。

## 交接 B4（contract，后端为主）
- 删后端死端点：`save_procedure`(PUT chapters/steps 装配)/`apply-marks`/`apply-layer-roles`/`convert_*` + 相关 schema（`LayerApplyIn/Result`、`ApplyMarksResult`）+ `types/node.ts` 里现仅前端遗留的 Layer/Apply 类型。
- 停双写 + 删 `ProcedureChapter`/`ProcedureStep` 表 + `numbering_service`/`node_sync`/`chapter_service` 脚手架 + 重建 dev.db。
- `asset_service._scan_referenced_asset_ids` 改扫 `ProcedureNode.body`（见 [[unified-node-model-direction]] B2 待办①）。
