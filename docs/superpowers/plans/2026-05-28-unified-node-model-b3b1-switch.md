# 统一节点模型 B3b-1 — 切换默认编辑器到统一节点编辑器 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 去掉 `?editor=node` flag、让 `ProcedureEditorView` 默认（`/edit` 与 `/view`）渲染统一节点编辑器（`NodeTreePanel`+`NodeDetailPanel` 绑 `nodeEditor` store），复用既有 shell（顶栏/Word 预览/元数据/附件/版本/对话框），元数据改即时存，新面板加只读模式；旧结构编辑代码休眠（B3b-2 删）。

**Architecture:** Strategy A「复用 shell、只换核心」。`ProcedureEditorView` 保留生命周期/元数据/附件/版本/Word 预览/只读 `/view`，仅把树+详情换成 `nodeEditor` 驱动的新面板。`procedureEditor` store 收窄为「元数据 store」：`setMetaField` 改为乐观本地 + 防抖即时 `updateProcedure`（去 dirty/save_procedure）。`EditorTopBar` 去 Save、撤销改接 `nodeEditor.undo`、加 autosave 指示。新面板加 `readonly` prop 供 `/view`。B3a-2 的独立壳 `NodeEditorView` 在本期变为死代码（B3b-2 删）。

**Tech Stack:** Vue 3 `<script setup>`、Pinia（options store）、Element Plus、`@vueuse/core`（`useDebounceFn`）、vue-router、TypeScript、vitest + `@vue/test-utils`。前端测试 `cd frontend && npx vitest run <file>`；类型 `npx vue-tsc --noEmit`；lint `npx eslint <files> --max-warnings 0`。

**Spec:** `docs/superpowers/specs/2026-05-28-unified-node-model-b3b-switch-delete-design.md`（B3b 设计）+ 母 spec `2026-05-28-unified-node-model-b3-frontend-design.md`。

**B3a 已交付（本计划消费/改造）：** `nodeEditor` store（`load/select/toggleExpand/setLevel/setKind/toggleSkip/batchSetLevel/batchSetKind/confirmReview/createNode/removeNode/reorder/updateBody/updateForm/undo`；getters `rows/reviewCount/canUndo/selectedNode`；state `nodes/selectedId/selection/search/reviewOnly`）；`NodeTreePanel`/`NodeTreeRow`/`NodeDetailPanel`；`utils/nodeTreeDnd`。`RichTextEditor` 已有 `readonly?:boolean`（默认 false），`StepFormFields` 已有 `readonly?:boolean`。

---

## 与 spec 的有意偏差（trade-off，commit 写理由）
1. **复用 `setMetaField` 作为即时存入口**（实现 spec 的「updateMeta」语义），不新增并行 `updateMeta` action——`ProcedureDetailsPanel` 已全部走 `setMetaField`，复用 = 零面板改动、DRY。
2. **防抖（500ms）合并 flush + 成功仅同步 revision**（不整对象覆盖，避免冲掉 flush 期间的并发本地编辑）——spec 未细化，为正确性/性能所需。`ProcedureUpdate` 必填 `name`+`level_of_use`，故 flush 发**全量当前 meta**。
3. **`NodeEditorView.vue` 及其 spec 本期不删**（去 gate 后变死代码）；删除留 B3b-2（spec 删除清单含它）。其 autosave `$onAction` 模式**复制**进 `EditorTopBar`（非搬移）。
4. **本期不用 `useEditorKeyboard`/`useEditorPersistence`**（键盘延后 β；persistence 是 dirty 模型概念）。文件本身留到 B3b-2 删。
5. **`ProcedureEditorView` 集成测试从简**（mock vue-router + stores、stub 子组件，断言「无 gate、渲染新面板、调 nodeEditor.load、readonly 透传」）；完整集成由 Task 7 手动验收 `/edit`+`/view` 覆盖（镜像 B3a-2「gate 不重型挂载」偏差）。
6. **`EditorTopBar` 删 redo 按钮**（`nodeEditor` 无 redo；spec 称隐藏/禁用）。

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `src/store/procedureEditor.ts` | `setMetaField` 改即时（乐观 + 防抖 `updateProcedure`）；加 `_scheduleMetaFlush`/`_flushMeta` + 模块级 timer | 修改 |
| `src/components/editor/NodeTreeRow.vue` | 加 `readonly` prop：隐藏 checkbox/chip/删除、禁拖拽 | 修改 |
| `src/components/editor/NodeTreePanel.vue` | 加 `readonly` prop：隐藏新增/γ 浮动条、透传 readonly 给行 | 修改 |
| `src/components/editor/NodeDetailPanel.vue` | 加 `readonly` prop：隐藏 level/kind/skip/review 确认/附件编辑、body+表单只读 | 修改 |
| `src/components/editor/EditorTopBar.vue` | 去 Save+未保存 chip+redo；撤销改接 `nodeEditor`；加 autosave 指示 | 修改 |
| `src/views/procedures/ProcedureEditorView.vue` | 去 gate；默认渲染新面板（绑 nodeEditor）；onMounted 双 load；`:readonly="!editable"`；去 dirty/save/persistence/keyboard | 重写（同形 shell） |
| `tests/unit/...` | 各文件 vitest | 增/改 |

---

## Task 1: `procedureEditor.setMetaField` 改即时（乐观 + 防抖 `updateProcedure`）

**Files:**
- Modify: `src/store/procedureEditor.ts`
- Test: `tests/unit/store/procedureEditor.metaImmediate.spec.ts`（新建）

**背景**：当前 `setMetaField`（约 :956）只改本地 + 置 `metaDirty=true`，靠批量 `save_procedure` 落库。本任务改为乐观本地 + 防抖即时 `updateProcedure`（meta-only PUT，`api/procedures.ts` 已有，且 `ProcedureDetailView` 已在生产用它做 meta 更新——后端 PUT 对「无 chapters/steps」的 payload 不动结构，安全）。`ProcedureUpdate` 必填 `name`+`level_of_use`，故发全量当前 meta。

- [ ] **Step 1: 写失败测试**

Create `tests/unit/store/procedureEditor.metaImmediate.spec.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { ProcedureMeta } from '@/types/procedure'

const { updateSpy, reloadDetailSpy } = vi.hoisted(() => ({
  updateSpy: vi.fn(),
  reloadDetailSpy: vi.fn(),
}))
// store 顶层 import 的 api/procedures 函数都给 mock，避免真实请求 / import 副作用。
vi.mock('@/api/procedures', () => ({
  updateProcedure: updateSpy,
  fetchProcedureDetail: reloadDetailSpy,
  saveProcedure: vi.fn(),
  applyMarks: vi.fn(),
  applyLayerRolesApi: vi.fn(),
}))

import { useProcedureEditorStore } from '@/store/procedureEditor'

// ProcedureMeta 字段多，只填代码路径用到的，其余 cast 收口。
function meta(over: Partial<ProcedureMeta> = {}): ProcedureMeta {
  return {
    id: 'p1', code: 'C-1', name: 'N', level_of_use: 'reference',
    description: '', risk_level: 1, quality_level: 1, custom_values: {},
    version_update_notes: '', signoff_enabled: false,
    revision: 3, version: 1, status: 'DRAFT', is_current: true,
    version_change_log: [],
    ...over,
  } as unknown as ProcedureMeta
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.useFakeTimers()
  updateSpy.mockReset()
  reloadDetailSpy.mockReset()
})
afterEach(() => vi.useRealTimers())

describe('procedureEditor.setMetaField — immediate (debounced) save', () => {
  it('optimistically updates local then flushes FULL meta via updateProcedure after debounce', async () => {
    updateSpy.mockResolvedValue(meta({ revision: 4 }))
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.setMetaField('name', 'New Name')
    expect(store.procedure!.name).toBe('New Name') // optimistic immediately
    expect(updateSpy).not.toHaveBeenCalled() // debounced
    await vi.advanceTimersByTimeAsync(500)
    expect(updateSpy).toHaveBeenCalledTimes(1)
    expect(updateSpy).toHaveBeenCalledWith(
      'p1',
      expect.objectContaining({ name: 'New Name', level_of_use: 'reference' }),
      3,
    )
    expect(store.procedure!.revision).toBe(4) // revision synced from result
  })

  it('coalesces rapid edits into one flush carrying all changed fields', async () => {
    updateSpy.mockResolvedValue(meta({ revision: 4 }))
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.setMetaField('name', 'A')
    store.setMetaField('description', 'D')
    await vi.advanceTimersByTimeAsync(500)
    expect(updateSpy).toHaveBeenCalledTimes(1)
    expect(updateSpy).toHaveBeenCalledWith('p1', expect.objectContaining({ name: 'A', description: 'D' }), 3)
  })

  it('does not flush when not editable', async () => {
    const store = useProcedureEditorStore()
    store.procedure = meta({ status: 'PUBLISHED' }) // editable=false
    store.setMetaField('name', 'X')
    await vi.advanceTimersByTimeAsync(500)
    expect(updateSpy).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/store/procedureEditor.metaImmediate.spec.ts`
Expected: FAIL — `setMetaField` 仍是 metaDirty 版（`updateProcedure` 不被调用 / revision 不变）。

- [ ] **Step 3: 实现（store）**

In `src/store/procedureEditor.ts`:

(a) 确保从 `@/api/procedures` import 了 `updateProcedure`（在既有 import 行追加；该文件已 import `saveProcedure` 等）。确保从 `@/types/procedure` import 了 `ProcedureUpdate`（在既有类型 import 追加）。

(b) 在文件顶层（import 之后、`defineStore` 之前）加模块级防抖句柄：

```typescript
const META_FLUSH_MS = 500
let metaFlushTimer: ReturnType<typeof setTimeout> | null = null
```

(c) 把现有 `setMetaField`（约 :956-960）整体替换为下面三个 action（`setMetaField` 改写 + 新增 `_scheduleMetaFlush`/`_flushMeta`）：

```typescript
    // 程序级元字段编辑（详情折叠面板）。即时·乐观写：本地先改 + 防抖 flush（去 dirty/批量 save）。
    setMetaField<K extends keyof ProcedureMeta>(key: K, value: ProcedureMeta[K]): void {
      if (!this.procedure) return
      this.procedure[key] = value // 乐观本地
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
        // 只同步 revision，避免冲掉 flush 期间的并发本地编辑（http 拦截器处理错误）。
        if (this.procedure && this.procedure.id === updated.id) this.procedure.revision = updated.revision
      } catch {
        await this.reload() // 失败（如 412）→ 重取同步
      }
    },
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/store/procedureEditor.metaImmediate.spec.ts`
Expected: PASS（3）。

- [ ] **Step 5: 修既有 setMetaField/metaDirty 断言（若有）**

Run: `cd frontend && grep -rn "setMetaField\|metaDirty" tests/unit/`
若 `tests/unit/store/procedureEditorStore.spec.ts`（或类似）有断言 `setMetaField` 置 `metaDirty=true` / 进 dirty 的用例：该行为已变（即时存、不再 metaDirty）。最小改动让其反映新行为——把这类断言改为「`setMetaField` 后 `this.procedure[key]` 被更新」（去掉 `metaDirty`/`isDirty` 断言），或若该用例整体在测旧批量保存路径则标注 `it.skip` 并在注释写「B3b-1 改即时存，旧 dirty 路径 B3b-2 删」。**不要**改动与 setMetaField 无关的既有用例。

- [ ] **Step 6: 运行确认通过 + 类型**

Run: `cd frontend && npx vitest run tests/unit/store/` 然后 `npx vue-tsc --noEmit`
Expected: store 测试全绿；无新增类型错误。

- [ ] **Step 7: Commit**

```bash
git add src/store/procedureEditor.ts tests/unit/store/procedureEditor.metaImmediate.spec.ts
# 若 Step 5 改了既有 spec，一并 add
git commit -m "feat(fe/procedureEditor): setMetaField immediate optimistic+debounced updateProcedure (B3b-1)"
```

---

## Task 2: `NodeTreeRow` 加 `readonly` prop

**Files:**
- Modify: `src/components/editor/NodeTreeRow.vue`
- Test: `tests/unit/NodeTreeRow.spec.ts`（追加）

- [ ] **Step 1: 写失败测试**

Append to `tests/unit/NodeTreeRow.spec.ts`（复用文件已有 `treeRow`/`mountRow`/`baseProps`；`mountRow(row, extra)` 第二参可传 `{ readonly: true }`）:

```typescript
describe('NodeTreeRow — readonly', () => {
  it('hides checkbox / chip / delete and is not draggable when readonly', () => {
    const w = mountRow(treeRow(), { readonly: true })
    expect(w.find('.ntr-check').exists()).toBe(false)
    expect(w.findComponent({ name: 'ElDropdown' }).exists()).toBe(false)
    expect(w.find('.ntr-del').exists()).toBe(false)
    expect((w.find('.ntr').element as HTMLElement).getAttribute('draggable')).toBe('false')
  })

  it('still shows code + title + review badge when readonly', () => {
    const w = mountRow(treeRow({ mark_status: 'review' }, { title: '安全须知' }), { readonly: true })
    expect(w.text()).toContain('安全须知')
    expect(w.find('.ntr-review').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/NodeTreeRow.spec.ts`
Expected: FAIL — readonly 时仍渲染 checkbox/chip/del、draggable 仍 "true"。

- [ ] **Step 3: 实现**

In `src/components/editor/NodeTreeRow.vue`:

(a) `interface Props` 加 `readonly`（放在 `dropHint` 后）：

```typescript
interface Props {
  row: TreeRow
  selected: boolean
  selectedForMark: boolean
  dropHint: '' | 'before' | 'after'
  readonly?: boolean
}
```

(b) 模板根 `div.ntr` 的 `draggable="true"` 改为 `:draggable="!readonly"`。

(c) checkbox、`.ntr-actions`（chip 的 `<span>`）、`.ntr-del` 三处各加 `v-if="!readonly"`：

```vue
    <el-checkbox
      v-if="!readonly"
      :model-value="selectedForMark"
      class="ntr-check"
      @click.stop="onCheck"
    />
    <span v-if="!readonly" class="ntr-actions" @click.stop>
```
```vue
    <el-button v-if="!readonly" class="ntr-del" size="small" text title="删除" @click.stop="emit('remove')">✕</el-button>
```

（caret/code/title/review 徽章不动；拖拽事件 handler 保留——`draggable=false` 时不会触发。）

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/NodeTreeRow.spec.ts`
Expected: PASS（既有 8 + 新 2）。

- [ ] **Step 5: 类型 + lint**

Run: `cd frontend && npx vue-tsc --noEmit && npx eslint src/components/editor/NodeTreeRow.vue tests/unit/NodeTreeRow.spec.ts --max-warnings 0`
Expected: 干净。

- [ ] **Step 6: Commit**

```bash
git add src/components/editor/NodeTreeRow.vue tests/unit/NodeTreeRow.spec.ts
git commit -m "feat(fe/NodeTreeRow): readonly prop (hide checkbox/chip/delete, no drag) (B3b-1)"
```

---

## Task 3: `NodeTreePanel` 加 `readonly` prop

**Files:**
- Modify: `src/components/editor/NodeTreePanel.vue`
- Test: `tests/unit/NodeTreePanel.spec.ts`（追加）

- [ ] **Step 1: 写失败测试**

Append to `tests/unit/NodeTreePanel.spec.ts`（复用文件已有 `n`；`setup` 不传 props，本测试单独 mount 传 `readonly`）。在文件顶部已 import 的基础上追加用例：

```typescript
describe('NodeTreePanel — readonly', () => {
  it('hides add button and floating bar; passes readonly to rows', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useNodeEditorStore()
    store.procedureId = 'p1'
    store.nodes = [n({ id: 'a', heading_level: 1, body: '<p>A</p>' })]
    store.selectedId = 'a'
    store.selection = new Set(['a']) // 即便有选中，readonly 也不显浮动条
    const w = mount(NodeTreePanel, {
      props: { readonly: true },
      global: { plugins: [ElementPlus, pinia] },
      attachTo: document.body,
    })
    expect(w.find('.np-add').exists()).toBe(false)
    expect(w.find('.np-bar').exists()).toBe(false)
    expect(w.findComponent({ name: 'NodeTreeRow' }).props('readonly')).toBe(true)
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/NodeTreePanel.spec.ts`
Expected: FAIL — readonly 时仍渲染 `.np-add`、`.np-bar`，行未收到 readonly。

- [ ] **Step 3: 实现**

In `src/components/editor/NodeTreePanel.vue`:

(a) 在 `<script setup>` 顶部（`const store = ...` 上方）加 props：

```typescript
const props = withDefaults(defineProps<{ readonly?: boolean }>(), { readonly: false })
```

(b) 模板「新增节点」按钮加 `v-if="!props.readonly"`：

```vue
      <el-button v-if="!props.readonly" class="np-add" size="small" @click="addNode">＋ 新增节点</el-button>
```

(c) γ 浮动条外层 `div.np-bar` 的 `v-if` 改为同时要求非只读：

```vue
    <div v-if="!props.readonly && store.selection.size" class="np-bar">
```

(d) `<NodeTreeRow>` 加 `:readonly="props.readonly"`（与既有绑定并列）：

```vue
      <NodeTreeRow
        v-for="row in store.rows"
        :key="row.node.id"
        :row="row"
        :readonly="props.readonly"
        :selected="store.selectedId === row.node.id"
        :selected-for-mark="store.selection.has(row.node.id)"
        :drop-hint="hintFor(row)"
        @select="onSelect(row.node.id)"
        @toggle="store.toggleExpand(row.node.id)"
        @check="(shift: boolean) => onCheck(row.node.id, shift)"
        @chip="(c: string) => onChip(row.node.id, c)"
        @remove="store.removeNode(row.node.id)"
        @dragstart="onDragStart(row.node.id)"
        @dragover="(ev: DragEvent) => onDragOver(row.node.id, ev)"
        @drop="onDrop(row.node.id)"
        @dragend="onDragEnd"
      />
```

（搜索 + review 计数/过滤/下一个 在只读下保留供浏览，不动。）

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/NodeTreePanel.spec.ts`
Expected: PASS（既有 8 + 新 1）。

- [ ] **Step 5: 类型 + lint**

Run: `cd frontend && npx vue-tsc --noEmit && npx eslint src/components/editor/NodeTreePanel.vue tests/unit/NodeTreePanel.spec.ts --max-warnings 0`
Expected: 干净。

- [ ] **Step 6: Commit**

```bash
git add src/components/editor/NodeTreePanel.vue tests/unit/NodeTreePanel.spec.ts
git commit -m "feat(fe/NodeTreePanel): readonly prop (hide add/floating-bar, thread to rows) (B3b-1)"
```

---

## Task 4: `NodeDetailPanel` 加 `readonly` prop

**Files:**
- Modify: `src/components/editor/NodeDetailPanel.vue`
- Test: `tests/unit/NodeDetailPanel.spec.ts`（追加）

- [ ] **Step 1: 写失败测试**

Append to `tests/unit/NodeDetailPanel.spec.ts`（复用文件已有 `n`/`stubs`；新增一个支持 props 的 mount 助手）:

```typescript
describe('NodeDetailPanel — readonly', () => {
  function mountRO() {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useNodeEditorStore()
    const w = mount(NodeDetailPanel, {
      props: { readonly: true },
      global: { plugins: [ElementPlus, pinia], stubs },
      attachTo: document.body,
    })
    return { w, store }
  }

  it('hides level/kind/skip controls, review confirm, and attachment add when readonly', async () => {
    const { w, store } = mountRO()
    store.nodes = [n({ id: 'a', kind: 'step', mark_status: 'review', input_schema: { type: 'CHECK' } })]
    store.selectedId = 'a'
    await w.vm.$nextTick()
    expect(w.find('.kind-switch').exists()).toBe(false)
    expect(w.find('.confirm-review').exists()).toBe(false)
    expect(w.find('.add-mark').exists()).toBe(false)
  })

  it('passes readonly to RichTextEditor and StepFormFields', async () => {
    const { w, store } = mountRO()
    store.nodes = [n({ id: 'a', kind: 'step', input_schema: { type: 'CHECK' } })]
    store.selectedId = 'a'
    await w.vm.$nextTick()
    expect(w.findComponent({ name: 'RichTextEditor' }).props('readonly')).toBe(true)
    expect(w.findComponent({ name: 'StepFormFields' }).props('readonly')).toBe(true)
  })
})
```

注：`stubs` 里 `RichTextEditor`/`StepFormFields` 已带 `name` 与 `readonly`/`schema` props（B3a-2 修过）；若 `RichTextEditor` stub 的 props 未含 `readonly`，在该 stub 的 `props` 数组加 `'readonly'`，`StepFormFields` 同理已含 `readonly`。

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/NodeDetailPanel.spec.ts`
Expected: FAIL — readonly 时仍渲染 kind-switch/confirm-review/add-mark；子组件未收到 readonly。

- [ ] **Step 3: 实现**

In `src/components/editor/NodeDetailPanel.vue`:

(a) `<script setup>` 顶部（`const store = ...` 上方）加 props：

```typescript
const props = withDefaults(defineProps<{ readonly?: boolean }>(), { readonly: false })
```

(b) 层级/kind/skip 的 `<el-form label-position="top">`（含「层级」select 与 `.inline` 的两个 switch）整块加 `v-if="!props.readonly"`：

```vue
    <el-form v-if="!props.readonly" label-position="top">
      <el-form-item label="层级">
        <el-select :model-value="node.heading_level" @change="onLevel">
          <el-option v-for="l in LEVELS" :key="String(l.value)" :value="l.value as number" :label="l.label" />
        </el-select>
      </el-form-item>
      <div class="inline">
        <el-form-item label="作为步骤（带执行表单）" class="kind-switch">
          <el-switch :model-value="node.kind === 'step'" @change="onKindSwitch" />
        </el-form-item>
        <el-form-item label="跳号">
          <el-switch :model-value="node.skip_numbering" @change="onSkip" />
        </el-form-item>
      </div>
    </el-form>
```

(c) body 的 `<RichTextEditor>` 加 `:readonly="props.readonly"`：

```vue
        <RichTextEditor
          :key="`body-${node.id}`"
          :model-value="node.body"
          variant="full"
          :readonly="props.readonly"
          :procedure-id="procId"
          placeholder="输入正文…（首个块级元素文本作为标题）"
          @update:model-value="pushBody"
        />
```

(d) step 表单类型 `<el-select :model-value="schema.type" @change="onTypeChange">` 加 `:disabled="props.readonly"`；`<StepFormFields>` 的 `:readonly="false"` 改为 `:readonly="props.readonly"`：

```vue
            <el-select :model-value="schema.type" :disabled="props.readonly" @change="onTypeChange">
```
```vue
              <div class="cp-config"><StepFormFields :schema="schema" :readonly="props.readonly" @update:schema="onSchema" /></div>
```

(e) 附件标记：每行的删除按钮、两个 `el-input`、`el-select` 用 `:disabled="props.readonly"`；「+ 附件标记」按钮加 `v-if="!props.readonly"`。最小改动——只需保证只读不可改：给 `.mark-row` 内三个输入 + 删除按钮加 `:disabled="props.readonly"`，并给 `.add-mark` 加 `v-if="!props.readonly"`：

```vue
        <div v-for="(m, i) in marks" :key="i" class="mark-row">
          <el-input :model-value="m.filename" placeholder="文件名" :disabled="props.readonly" @input="(v: string) => updMark(i, { filename: v })" />
          <el-select :model-value="m.kind" class="mark-kind" :disabled="props.readonly" @change="(v: string) => updMark(i, { kind: v })">
            <el-option v-for="k in ATTACH_KINDS" :key="k.value" :value="k.value" :label="k.label" />
          </el-select>
          <el-input :model-value="m.note" placeholder="备注" :disabled="props.readonly" @input="(v: string) => updMark(i, { note: v })" />
          <el-button v-if="!props.readonly" size="small" text @click="removeMark(i)">✕</el-button>
        </div>
        <el-button v-if="!props.readonly" class="add-mark" size="small" @click="addMark">+ 附件标记</el-button>
```

(f) review 确认条加只读 gate：

```vue
    <div v-if="node.mark_status === 'review' && !props.readonly" class="review-bar">
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/NodeDetailPanel.spec.ts`
Expected: PASS（既有 6 + 新 2）。

- [ ] **Step 5: 类型 + lint**

Run: `cd frontend && npx vue-tsc --noEmit && npx eslint src/components/editor/NodeDetailPanel.vue tests/unit/NodeDetailPanel.spec.ts --max-warnings 0`
Expected: 干净。

- [ ] **Step 6: Commit**

```bash
git add src/components/editor/NodeDetailPanel.vue tests/unit/NodeDetailPanel.spec.ts
git commit -m "feat(fe/NodeDetailPanel): readonly prop (hide edit controls, body/form readonly) (B3b-1)"
```

---

## Task 5: `EditorTopBar` 去 Save、撤销改接 `nodeEditor`、加 autosave 指示

**Files:**
- Modify: `src/components/editor/EditorTopBar.vue`
- Test: `tests/unit/EditorTopBar.spec.ts`（替换为新内容）

**背景**：顶栏保留生命周期（PDF/发布/升级/丢弃/复制）+ 面包屑（读 `procedureEditor.procedure`/`editable`）。结构撤销改接 `nodeEditor.undo`/`canUndo`；删 Save 按钮 + 未保存 chip + redo 按钮；加 autosave 指示（`$onAction` 计 `nodeEditor` mutating actions，复制自 `NodeEditorView`）。

- [ ] **Step 1: 写失败测试（替换 spec）**

Replace `tests/unit/EditorTopBar.spec.ts` with:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import EditorTopBar from '@/components/editor/EditorTopBar.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { useNodeEditorStore } from '@/store/nodeEditor'
import type { ProcedureMeta } from '@/types/procedure'

// 控制 nodeEditor 真实 action 的网络往返，以驱动 $onAction（autosave 指示）。
const { batchSpy } = vi.hoisted(() => ({ batchSpy: vi.fn() }))
vi.mock('@/api/nodes', () => ({
  batchUpdateNodes: batchSpy,
  listNodes: vi.fn(),
  patchNode: vi.fn(),
  createNode: vi.fn(),
  deleteNode: vi.fn(),
  reorderNodes: vi.fn(),
}))

function meta(over: Partial<ProcedureMeta> = {}): ProcedureMeta {
  return {
    id: 'p1', code: 'C-1', name: '示例', level_of_use: 'reference',
    description: '', risk_level: 1, quality_level: 1, custom_values: {},
    version_update_notes: '', signoff_enabled: false,
    revision: 1, version: 1, status: 'DRAFT', is_current: true,
    folder_full_path: '根', version_change_log: [],
    ...over,
  } as unknown as ProcedureMeta
}

function setup(over: Partial<ProcedureMeta> = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const proc = useProcedureEditorStore()
  proc.procedure = meta(over)
  const node = useNodeEditorStore()
  const w = mount(EditorTopBar, { global: { plugins: [ElementPlus, pinia] }, attachTo: document.body })
  return { w, proc, node }
}

beforeEach(() => vi.restoreAllMocks())

describe('EditorTopBar (B3b-1)', () => {
  it('renders code + name', () => {
    const { w } = setup()
    expect(w.text()).toContain('C-1')
    expect(w.text()).toContain('示例')
  })

  it('has NO save button', () => {
    const { w } = setup()
    expect(w.findAll('button').some((b) => b.text().includes('保存'))).toBe(false)
  })

  it('undo disabled until canUndo, then calls nodeEditor.undo', async () => {
    const { w, node } = setup()
    const undo = vi.spyOn(node, 'undo').mockResolvedValue()
    const btn = w.find('.etb-undo')
    expect(btn.attributes('disabled')).toBeDefined()
    node.undoStack = [async () => {}]
    await w.vm.$nextTick()
    expect(w.find('.etb-undo').attributes('disabled')).toBeUndefined()
    await w.find('.etb-undo').trigger('click')
    expect(undo).toHaveBeenCalled()
  })

  it('shows autosave indicator that flips while a mutating action is in-flight', async () => {
    const { w, node } = setup()
    node.procedureId = 'p1' // 让真实 setLevel 不早退
    // batchUpdateNodes 挂起 → setLevel 在途；$onAction 才能驱动 saving。
    let release!: (v: unknown) => void
    batchSpy.mockReturnValue(new Promise((res) => { release = res }))
    expect(w.find('.etb-save').text()).toContain('已保存')
    void node.setLevel('x', 1) // 真实 action（非 mock），$onAction 触发
    await w.vm.$nextTick()
    expect(w.find('.etb-save').text()).toContain('保存中')
    release([]) // resolve：setLevel 用空 list 收尾
    await flushPromises()
    expect(w.find('.etb-save').text()).toContain('已保存')
  })

  it('emits lifecycle events (publish/preview-pdf/copy)', async () => {
    const { w } = setup()
    await w.findAll('button').find((b) => b.text() === '发布')!.trigger('click')
    await w.findAll('button').find((b) => b.text() === 'PDF 预览')!.trigger('click')
    expect(w.emitted('publish')).toBeTruthy()
    expect(w.emitted('preview-pdf')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/EditorTopBar.spec.ts`
Expected: FAIL — 现版仍有保存按钮、撤销走 procedureEditor、无 `.etb-undo`/`.etb-save` class。

- [ ] **Step 3: 实现（替换 EditorTopBar.vue）**

Replace `src/components/editor/EditorTopBar.vue` with:

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import StatusTag from '@/components/StatusTag.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { useNodeEditorStore } from '@/store/nodeEditor'
import type { ProcedureStatus } from '@/types/procedure'

// 编辑器顶栏（B3b-1）：面包屑 + 状态 + 撤销（nodeEditor）+ autosave 指示 + 生命周期按钮。
// 即时·乐观写：无 Save / dirty。
const emit = defineEmits<{
  (e: 'publish'): void
  (e: 'back'): void
  (e: 'upgrade'): void
  (e: 'discard'): void
  (e: 'copy'): void
  (e: 'preview-pdf'): void
}>()

const store = useProcedureEditorStore()
const node = useNodeEditorStore()
const p = computed(() => store.procedure)
const showPublish = computed(() => store.editable)
const showUpgrade = computed(() => !!p.value && p.value.is_current && p.value.status === 'PUBLISHED')
const showDiscard = computed(
  () => !!p.value && p.value.is_current && p.value.status === 'DRAFT' && p.value.version > 1,
)

// autosave 指示：$onAction 计 nodeEditor mutating actions（复制自退役的 NodeEditorView）。
const inflight = ref(0)
const saving = ref(false)
const MUTATING = new Set([
  'setLevel', 'setKind', 'toggleSkip', 'batchSetLevel', 'batchSetKind',
  'confirmReview', 'createNode', 'removeNode', 'reorder', 'updateBody', 'updateForm', 'undo',
])
node.$onAction(({ name, after, onError }) => {
  if (!MUTATING.has(name)) return
  inflight.value++
  saving.value = true
  const done = (): void => {
    inflight.value = Math.max(0, inflight.value - 1)
    if (inflight.value === 0) saving.value = false
  }
  after(done)
  onError(done)
})
</script>

<template>
  <div class="topbar">
    <div class="left">
      <el-button text size="small" @click="emit('back')">← 返回</el-button>
      <span class="code">{{ p?.code }}</span>
      <span class="name">{{ p?.name }}</span>
      <span class="path">{{ p?.folder_full_path }}</span>
      <StatusTag v-if="p" :status="p.status as ProcedureStatus" />
      <el-tag v-if="p" size="small" type="info">v{{ p.version }}</el-tag>
    </div>

    <div v-if="store.editable" class="right">
      <el-button class="etb-undo" size="small" :disabled="!node.canUndo" title="撤销 (节点编辑)" @click="node.undo()">↶ 撤销</el-button>
      <span class="etb-save" :class="{ 'is-saving': saving }">{{ saving ? '保存中…' : '✓ 已保存' }}</span>
      <el-button size="small" @click="emit('preview-pdf')">PDF 预览</el-button>
      <el-button v-if="showPublish" size="small" type="primary" @click="emit('publish')">发布</el-button>
      <el-button v-if="showUpgrade" size="small" @click="emit('upgrade')">升级版本</el-button>
      <el-dropdown trigger="click">
        <el-button size="small" text>⋮</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-if="showDiscard" @click="emit('discard')">丢弃此 DRAFT</el-dropdown-item>
            <el-dropdown-item @click="emit('copy')">复制为新程序</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<style scoped>
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
  background: var(--el-bg-color, #fff);
}
.left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow: hidden;
}
.code { font-weight: 600; color: #606266; }
.name { font-weight: 600; }
.path { color: #909399; font-size: 12px; }
.right { display: flex; align-items: center; gap: 8px; flex: none; }
.etb-save { font-size: 12px; color: #67c23a; }
.etb-save.is-saving { color: #909399; }
</style>
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/EditorTopBar.spec.ts`
Expected: PASS（5）。

- [ ] **Step 5: 类型 + lint**

Run: `cd frontend && npx vue-tsc --noEmit && npx eslint src/components/editor/EditorTopBar.vue tests/unit/EditorTopBar.spec.ts --max-warnings 0`
Expected: 干净。

- [ ] **Step 6: Commit**

```bash
git add src/components/editor/EditorTopBar.vue tests/unit/EditorTopBar.spec.ts
git commit -m "feat(fe/EditorTopBar): drop Save/redo, undo→nodeEditor, autosave indicator (B3b-1)"
```

---

## Task 6: `ProcedureEditorView` 去 gate、默认渲染统一编辑器

**Files:**
- Modify (rewrite): `src/views/procedures/ProcedureEditorView.vue`
- Test: `tests/unit/ProcedureEditorView.switch.spec.ts`（新建）

**背景**：去 `?editor=node` gate；主体恒渲染 `NodeTreePanel`+`NodeDetailPanel`（绑 `nodeEditor`，`:readonly="!editable"`）。保留 shell（顶栏/Word 预览/元数据/附件/版本/对话框）+ 生命周期 handler + meta load + `/edit→/view` 只读重定向 + 侧栏自动折叠。去 dirty/save/persistence/keyboard/kind/onDeleteSelected 等结构批量模型代码（旧 `procedureEditor` 结构 action 本期休眠，B3b-2 删）。

- [ ] **Step 1: 写失败测试**

Create `tests/unit/ProcedureEditorView.switch.spec.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import type { ProcedureMeta } from '@/types/procedure'

const { routeRef } = vi.hoisted(() => ({
  routeRef: { value: { params: { id: 'p1' }, query: {}, name: 'procedure-edit', path: '/procedures/p1/edit' } as Record<string, unknown> },
}))
vi.mock('vue-router', () => ({
  useRoute: () => routeRef.value,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  onBeforeRouteLeave: vi.fn(),
}))

import ProcedureEditorView from '@/views/procedures/ProcedureEditorView.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { useNodeEditorStore } from '@/store/nodeEditor'

function meta(over: Partial<ProcedureMeta> = {}): ProcedureMeta {
  return {
    id: 'p1', code: 'C-1', name: 'N', level_of_use: 'reference',
    description: '', risk_level: 1, quality_level: 1, custom_values: {},
    version_update_notes: '', signoff_enabled: false,
    revision: 1, version: 1, status: 'DRAFT', is_current: true,
    folder_full_path: '根', version_change_log: [], has_source_docx: false,
    ...over,
  } as unknown as ProcedureMeta
}

const stubs = {
  EditorTopBar: { template: '<div class="topbar-stub" />' },
  EditorPreviewPane: { template: '<div class="preview-stub" />' },
  NodeTreePanel: { name: 'NodeTreePanel', template: '<div class="tree-stub" />', props: ['readonly'] },
  NodeDetailPanel: { name: 'NodeDetailPanel', template: '<div class="detail-stub" />', props: ['readonly'] },
  ProcedureDetailsPanel: { template: '<div class="meta-stub" />' },
  AttachmentPanel: { template: '<div class="attach-stub" />' },
  CollapsiblePanel: { template: '<div><slot /></div>' },
  PublishChecklistDialog: { template: '<div />' },
  VersionActionDialog: { template: '<div />' },
  PdfPreviewDialog: { template: '<div />' },
}

function mountView(editable = true) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const proc = useProcedureEditorStore()
  vi.spyOn(proc, 'load').mockImplementation(async () => {
    proc.procedure = meta(editable ? {} : { status: 'PUBLISHED', is_current: true })
  })
  const node = useNodeEditorStore()
  const nodeLoad = vi.spyOn(node, 'load').mockResolvedValue()
  const w = mount(ProcedureEditorView, { global: { plugins: [ElementPlus, pinia], stubs } })
  return { w, proc, node, nodeLoad }
}

beforeEach(() => {
  routeRef.value = { params: { id: 'p1' }, query: {}, name: 'procedure-edit', path: '/procedures/p1/edit' }
  vi.clearAllMocks()
})

describe('ProcedureEditorView — unified editor switch (B3b-1)', () => {
  it('renders NodeTreePanel + NodeDetailPanel (no node-mode gate) and loads nodeEditor', async () => {
    const { w, nodeLoad } = mountView(true)
    await flushPromises()
    expect(w.find('.tree-stub').exists()).toBe(true)
    expect(w.find('.detail-stub').exists()).toBe(true)
    expect(nodeLoad).toHaveBeenCalledWith('p1')
  })

  it('passes readonly=false to panels when editable (draft current)', async () => {
    const { w } = mountView(true)
    await flushPromises()
    expect(w.findComponent({ name: 'NodeTreePanel' }).props('readonly')).toBe(false)
    expect(w.findComponent({ name: 'NodeDetailPanel' }).props('readonly')).toBe(false)
  })

  it('passes readonly=true to panels on /view (not editable)', async () => {
    routeRef.value = { params: { id: 'p1' }, query: {}, name: 'procedure-view', path: '/procedures/p1/view' }
    const { w } = mountView(false)
    await flushPromises()
    expect(w.findComponent({ name: 'NodeTreePanel' }).props('readonly')).toBe(true)
    expect(w.findComponent({ name: 'NodeDetailPanel' }).props('readonly')).toBe(true)
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/ProcedureEditorView.switch.spec.ts`
Expected: FAIL — 现版有 gate（mock route 无 `editor=node` 时走旧 ChapterTreePanel；无 `.tree-stub`/`.detail-stub`，`nodeEditor.load` 不被调）。

- [ ] **Step 3: 实现（重写 ProcedureEditorView.vue）**

Replace `src/views/procedures/ProcedureEditorView.vue` with:

```vue
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import EditorTopBar from '@/components/editor/EditorTopBar.vue'
import NodeTreePanel from '@/components/editor/NodeTreePanel.vue'
import NodeDetailPanel from '@/components/editor/NodeDetailPanel.vue'
import ProcedureDetailsPanel from '@/components/editor/ProcedureDetailsPanel.vue'
import PublishChecklistDialog from '@/components/editor/PublishChecklistDialog.vue'
import VersionActionDialog, {
  type VersionActionResult,
} from '@/components/version/VersionActionDialog.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { useNodeEditorStore } from '@/store/nodeEditor'
import { copyProcedure, deleteProcedure, transitionProcedure, upgradeVersion } from '@/api/procedures'
import { formatDateTime } from '@/utils/format'
import AttachmentPanel from '@/components/editor/AttachmentPanel.vue'
import PdfPreviewDialog from '@/components/PdfPreview/PdfPreviewDialog.vue'
import EditorPreviewPane from '@/components/editor/EditorPreviewPane.vue'
import CollapsiblePanel from '@/components/shared/CollapsiblePanel.vue'
import { useSidebar } from '@/composables/useSidebar'
import { shouldAutoCollapse } from '@/utils/editorFocus'
import type { PanelConfig } from '@/utils/collapsiblePanel'

// 统一节点编辑器（B3b-1）：默认（/edit 与 /view）渲染 NodeTreePanel+NodeDetailPanel（绑 nodeEditor）。
// 即时·乐观写：无 Save / dirty / 草稿持久化 / 离开守卫。生命周期与 meta 仍由 procedureEditor（slim）。
const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))
const store = useProcedureEditorStore()
const nodeStore = useNodeEditorStore()

const activeTab = ref<'node' | 'attach' | 'history'>('node')
const publishVisible = ref(false)
const copyVisible = ref(false)
const pdfPreviewVisible = ref(false)
const versionBusy = ref(false)

const sidebar = useSidebar()
const autoCollapsed = ref(false)
const priorCollapsed = ref<boolean | null>(null)
const DETAIL_CFG: PanelConfig = { defaultWidth: 360, min: 300, max: 700 }

// 即时写：结构与 meta 都已落库，PDF 预览直接打开（无需先存）。
function onPreviewPdf(): void {
  pdfPreviewVisible.value = true
}

async function onPublishConfirm(): Promise<void> {
  const p = store.procedure
  if (!p) return
  try {
    await transitionProcedure(p.id, { status: 'PUBLISHED' }, p.revision)
    publishVisible.value = false
    ElMessage.success('已发布')
    await store.reload()
  } catch {
    /* 拦截器已提示 */
  }
}

async function onUpgrade(): Promise<void> {
  const p = store.procedure
  if (!p) return
  try {
    await ElMessageBox.confirm('升级将归档当前版本并创建新草稿版本，是否继续？', '升级版本', {
      type: 'warning',
    })
  } catch {
    return
  }
  versionBusy.value = true
  try {
    const next = await upgradeVersion(p.id)
    ElMessage.success(`已创建 v${next.version} 草稿`)
    await router.push(`/procedures/${next.id}/edit`)
  } catch {
    /* 拦截器已提示 */
  } finally {
    versionBusy.value = false
  }
}

async function onDiscard(): Promise<void> {
  const p = store.procedure
  if (!p) return
  let reason: string
  try {
    const r = await ElMessageBox.prompt('请输入丢弃原因', '丢弃此草稿', {
      inputValidator: (v) => (v && v.trim() ? true : '原因必填'),
      type: 'warning',
    })
    reason = r.value
  } catch {
    return
  }
  versionBusy.value = true
  try {
    const result = await deleteProcedure(p.id, reason)
    if (result) {
      ElMessage.success(`已丢弃草稿，当前版本回到 v${result.new_current_version}`)
      await router.push(`/procedures/${result.new_current_id}`)
    } else {
      ElMessage.success('已删除')
      await router.push({ name: 'procedure-library' })
    }
  } catch {
    /* 拦截器已提示 */
  } finally {
    versionBusy.value = false
  }
}

async function onCopyConfirm(payload: VersionActionResult): Promise<void> {
  const p = store.procedure
  if (!p) return
  versionBusy.value = true
  try {
    const copy = await copyProcedure(p.id, {
      target_folder_id: payload.target_folder_id,
      name: payload.name || undefined,
    })
    copyVisible.value = false
    ElMessage.success(`已复制为 ${copy.code}`)
    await router.push(`/procedures/${copy.id}/edit`)
  } catch {
    /* 拦截器已提示 */
  } finally {
    versionBusy.value = false
  }
}

onMounted(async () => {
  await store.load(id.value)
  if (store.loadError) return
  // 访问 /edit 但不可编辑 → 跳只读 /view（不留历史）。
  if (route.name === 'procedure-edit' && !store.editable) {
    void router.replace({ name: 'procedure-view', params: { id: id.value } })
    return
  }
  await nodeStore.load(id.value) // 结构（即时·乐观）

  // Word 导入进入 → 专注模式：自动折叠侧边栏（离开恢复）。
  if (shouldAutoCollapse(route.query.from, sidebar.collapsed.value)) {
    priorCollapsed.value = sidebar.collapsed.value
    sidebar.collapsed.value = true
    autoCollapsed.value = true
    void router.replace({ path: route.path, query: {} })
  }
  watch(
    () => sidebar.collapsed.value,
    () => {
      autoCollapsed.value = false
    },
  )
})

onUnmounted(() => {
  if (autoCollapsed.value) {
    sidebar.collapsed.value = priorCollapsed.value ?? false
  }
})

function goBack(): void {
  void router.push({ name: 'procedure-library' })
}
</script>

<template>
  <div v-loading="store.loading" class="editor">
    <template v-if="store.loadError">
      <el-result icon="error" title="加载失败">
        <template #extra>
          <el-button type="primary" @click="store.load(id)">重试</el-button>
        </template>
      </el-result>
    </template>

    <template v-else-if="store.procedure">
      <EditorTopBar
        @publish="publishVisible = true"
        @back="goBack"
        @upgrade="onUpgrade"
        @discard="onDiscard"
        @copy="copyVisible = true"
        @preview-pdf="onPreviewPdf"
      />

      <el-alert
        v-if="!store.editable"
        type="warning"
        :closable="false"
        show-icon
        class="ro-banner"
        :title="`只读模式：仅当前版本的草稿可编辑（当前 v${store.procedure.version} · ${store.procedure.status}）。`"
      />

      <div class="body">
        <EditorPreviewPane v-if="store.hasSourceDocx" :procedure-id="store.procedure.id" />
        <div class="left">
          <NodeTreePanel :readonly="!store.editable" />
        </div>
        <CollapsiblePanel
          label="节点详情"
          side="right"
          storage-key="smartsop.editor.detail"
          :config="DETAIL_CFG"
        >
          <div class="right-scroll">
            <ProcedureDetailsPanel />
            <el-tabs v-model="activeTab" class="tabs">
              <el-tab-pane label="节点详情" name="node">
                <div class="pane">
                  <NodeDetailPanel :readonly="!store.editable" />
                </div>
              </el-tab-pane>
              <el-tab-pane label="附件" name="attach">
                <AttachmentPanel
                  :procedure-id="store.procedure.id"
                  :editable="store.editable"
                  class="pane"
                />
              </el-tab-pane>
              <el-tab-pane label="版本历史" name="history">
                <el-timeline v-if="store.procedure.version_change_log.length" class="pane">
                  <el-timeline-item
                    v-for="(entry, i) in store.procedure.version_change_log"
                    :key="i"
                    :timestamp="formatDateTime(String(entry.changed_at ?? ''))"
                  >
                    {{ entry.change_type }} — {{ entry.description || '' }}
                  </el-timeline-item>
                </el-timeline>
                <el-empty v-else description="暂无版本记录（回退 / 升级见 Phase 7）" />
              </el-tab-pane>
            </el-tabs>
          </div>
        </CollapsiblePanel>
      </div>

      <PublishChecklistDialog v-model="publishVisible" @confirm="onPublishConfirm" />
      <VersionActionDialog
        v-model="copyVisible"
        title="复制为新程序"
        :need-reason="false"
        :need-folder="true"
        :need-name="true"
        :loading="versionBusy"
        @confirm="onCopyConfirm"
      />
      <PdfPreviewDialog v-model="pdfPreviewVisible" :procedure-id="store.procedure.id" />
    </template>
  </div>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 0px);
  min-height: 480px;
}
.ro-banner {
  border-radius: 0;
}
.body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.left {
  flex: 1;
  min-width: 280px;
  min-height: 0;
}
.right-scroll {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.tabs {
  flex: 1;
  padding: 0 14px;
}
.pane {
  padding: 8px 0 40px;
}
</style>
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/ProcedureEditorView.switch.spec.ts`
Expected: PASS（3）。

- [ ] **Step 5: 类型 + lint**

Run: `cd frontend && npx vue-tsc --noEmit && npx eslint src/views/procedures/ProcedureEditorView.vue tests/unit/ProcedureEditorView.switch.spec.ts --max-warnings 0`
Expected: 干净。注：`NodeEditorView.vue`、`useEditorPersistence`/`useEditorKeyboard` 不再被本文件 import，但文件仍在（B3b-2 删）；ESLint 不会因「存在未被引用的文件」报错。

- [ ] **Step 6: Commit**

```bash
git add src/views/procedures/ProcedureEditorView.vue tests/unit/ProcedureEditorView.switch.spec.ts
git commit -m "feat(fe/ProcedureEditorView): default to unified node editor, drop ?editor=node gate (B3b-1)"
```

---

## Task 7: 全量回归 + 类型 + lint + 手动 dev 验收（/edit 与 /view）

**Files:** 无新增

- [ ] **Step 1: 全部前端测试**

Run: `cd frontend && npx vitest run`
Expected: 全绿（旧 `ChapterTreePanel`/`TreeRow`/`ChapterDetailPanel`/`ContentDetailPanel`/`NodeEditorView`/`layerMark`/`procedureEditor` 等 spec 仍在仍绿——它们测的组件/代码本期未删，B3b-2 才删；本期改动文件的 spec 全绿）。记录总数（应 = 旧 baseline + 本期新增/改动用例，且无回归）。1 个先存 `ChapterDetailPanel` offsetHeight unhandled rejection 仍是已知量。

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无新增类型错误。

- [ ] **Step 3: Lint（本期改动文件）**

Run: `cd frontend && npx eslint src/store/procedureEditor.ts src/components/editor/EditorTopBar.vue "src/components/editor/NodeTree*.vue" src/components/editor/NodeDetailPanel.vue src/views/procedures/ProcedureEditorView.vue --max-warnings 0`
Expected: 0 warning/error。

- [ ] **Step 4: 手动 dev 验收（running-smartsop-dev + chrome-devtools）**

启动 dev（后端 8000 / 前端 5173，见 `running-smartsop-dev`；worktree 跑前端见下方「执行须知」）。

**/edit（可编辑草稿）**：开 `http://localhost:<port>/procedures/<草稿程序id>/edit`（**无** `?editor=node`）：
- 验证：默认即新编辑器（顶栏 + 节点树 + 详情）；行内 chip 改 level/kind 实时生效；新增/删除/拖拽；详情 body / step 表单 / 附件；撤销（顶栏 ↶）；autosave「保存中…/已保存」；**程序详情面板改名称/风险等级等 → 即时落库**（改完等 ~0.5s，刷新页面值仍在）；发布/升级/复制/丢弃/PDF 预览按钮在；Word 原文预览栏（若有源 docx）。
- **dev.db 陈旧注**：现有程序多为 0 个 ProcedureNode（B2a 起仅结构写触发 rebuild）。空树时可先在树里「＋ 新增节点」造数据验证；或换有 node 的程序。勿误判为 bug。

**/view（只读）**：开某非当前版本 `…/view`（或对已发布版点查看）：
- 验证：只读——无 chip/checkbox/新增/删除/拖拽、详情控件禁用/隐藏、body/表单只读；面包屑/版本历史/附件仍可看；顶栏动作组按 editable 隐藏。

记录验收要点（截图存 `.verify-screenshots/`，**勿** `rm -rf` 该目录——它含历史已跟踪截图）。

- [ ] **Step 5: Commit（若有修正）**

```bash
git add -A
git commit -m "chore(fe): type/lint/regression fixes for B3b-1"
```

---

## 执行须知（worktree）
- 前端 worktree 需 bootstrap `frontend/node_modules`（symlink 父 repo 的）。`.verify-screenshots/` 是**已跟踪**目录，勿删。
- 子代理从 worktree 派发默认 cwd 是父 repo——每个实现/测试命令用**绝对 worktree 路径**，commit 后验 `git rev-parse --abbrev-ref HEAD` = `feat/unified-node-model-b3b1`（或本次分支名）。
- 基线（合并前 main）：前端全测绿（B3a-2 合并后 444 passed + 1 先存失败）。

## 完成标准（B3b-1）
1. `/procedures/:id/edit` 与 `/view` **默认**渲染统一节点编辑器（`NodeTreePanel`+`NodeDetailPanel` 绑 `nodeEditor`），无 `?editor=node` gate。
2. `/view`（不可编辑）只读：新面板隐藏全部编辑能力、body/表单只读。
3. 顶栏：撤销 → `nodeEditor.undo`、autosave 指示、无 Save、生命周期按钮（发布/升级/丢弃/复制/PDF）保留可用。
4. 程序元数据即时·乐观存（`setMetaField` → 防抖 `updateProcedure`），无 dirty/Save。
5. 全 vitest 绿、`vue-tsc` 干净、改动文件 eslint 干净；`/edit` 与 `/view` 手动验收通过；后端不受影响。

## 交接 B3b-2（删旧）
- 删：`ChapterTreePanel`/`TreeRow`/`ChapterDetailPanel`/`ContentDetailPanel`/`StepDetailPanel`/`NodeEditorView.vue`、`utils/layerMark.ts`、`procedureEditor` 结构/save/layer/mark/转换/本地编辑死码（`buildPayload`/`save`/`applyIdMap`/`validateForSave`/`isDirty`/undo/redo/`metaDirty` 等）、前端 `saveProcedure()` 调用、`useEditorPersistence`/`useEditorKeyboard`、废测试（`ChapterTreePanel`/`TreeRow`/`ChapterDetailPanel`/`ContentDetailPanel`/`layerMark`/`applyLayerRoles`/markMode/`NodeEditorView` spec）。
- 改：`batchMark.ts` 去 `kind === 'chapter'` skip（:48）。
- 注：本期 `setMetaField` 已即时化，但 `metaDirty` state / `isDirty` 仍在（休眠）——B3b-2 随结构 dirty 一并删。
