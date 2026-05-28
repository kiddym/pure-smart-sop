# 统一节点模型 B3a-2 — 节点编辑器 UI 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `?editor=node` flag 下新建一个隔离的、消费 B3a-1 `nodeEditor` store 的节点编辑器（NodeEditorView + NodeTreePanel + NodeTreeRow + NodeDetailPanel），旧编辑器零改动仍默认；纯前端、即时·乐观·颗粒度写，全 vitest 覆盖。

**Architecture:** `ProcedureEditorView` 加一处 flag gate：`?editor=node` 时渲染独立 `NodeEditorView`（只 `nodeEditor.load(id)`，不碰 `procedureEditor`），否则旧编辑器原样。树面板渲染 `store.rows`（B3a-1 的派生 `TreeRow[]`），行内 chip 调单节点 `setLevel/setKind`，γ 多选浮动条调 `batchSetLevel/batchSetKind`，子树感知拖拽 → `reorder`，详情面板 body 走 `updateBody`、step 表单走 `updateForm`、review 确认走 `confirmReview`，撤销走 `undo`。服务端权威，前端不重算派生/编号。

**Tech Stack:** Vue 3 `<script setup>`、Pinia（options store）、Element Plus、`@wangeditor`（经既有 `RichTextEditor`）、`@vueuse/core`（`useDebounceFn`）、TypeScript、vitest + `@vue/test-utils`（`mount` + `global.plugins:[ElementPlus]` + `stubs` + `setActivePinia(createPinia())`）。前端测试 `cd frontend && npx vitest run <file>`；类型 `npx vue-tsc --noEmit`；lint `npx eslint <files> --max-warnings 0`。

**Spec:** `docs/superpowers/specs/2026-05-28-unified-node-model-b3a2-node-editor-ui-design.md`（本次设计）+ B3 母 spec `2026-05-28-unified-node-model-b3-frontend-design.md` + 统一模型 spec `2026-05-28-unified-node-model-design.md` §3/§6。

**B3a-1 已交付（本计划消费，勿改）：** `nodeEditor` store actions：`load/select/toggleExpand/setLevel/setKind/toggleSkip/batchSetLevel/confirmReview/createNode/removeNode/reorder/updateBody/updateForm/undo`；getters：`rows`(=`TreeRow[]`)/`nodeMap`/`reviewCount`/`selectedNode`/`canUndo`；state：`nodes/selectedId/expanded/search/reviewOnly/selection`。`TreeRow = { node: Node; title: string; hasChildren: boolean; expanded: boolean }`（行用 `r.node.id`）。

---

## 与 spec 的有意偏差（trade-off，commit 写理由）
1. **autosave 指示用 `NodeEditorView` 的 `store.$onAction` 计数**，不在 store 加 `saving` flag——避免给刚合并的 store 11 个 action 全套 try/finally；view 本就是指示的拥有者。
2. **虚拟列表延后**：MVP 用直接 `v-for` 渲染 `store.rows`（jsdom 可测、YAGNI）；大程序性能优化（移植 `useVirtualList`）留后续 pass。
3. **级联多选（勾选标题选整子树）延后**：MVP 多选 = 单勾 + shift 区间（`buildSelection`），覆盖批量清理主场景；`buildCascadeSelection` 复用留后续。
4. **gate 不写重型挂载单测**：`route.query.editor === 'node'` 是 1 行 computed，单测它需挂载整个旧 view（重）；由 Task 7 浏览器实测 + tsc 覆盖。

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `src/store/nodeEditor.ts` | 加 `batchSetKind(ids, kind)`（γ 浮动条「设为 step/普通」） | 修改（追加 action） |
| `src/utils/batchMark.ts` | `buildSelection` 的 `rows` 参数放宽为结构型 `SelectableRow`，兼容 node 行 | 修改（放宽类型） |
| `src/utils/nodeTreeDnd.ts` | `computeReorder(nodes, dragId, targetId, position)` 子树感知重排 | 创建 |
| `src/components/editor/NodeDetailPanel.vue` | 选中节点详情：body / level·kind·skip / step 表单 + attachment / review 确认 | 创建 |
| `src/components/editor/NodeTreeRow.vue` | 单行：caret、checkbox、level chip、code、title、review 徽章、删除、拖拽 | 创建 |
| `src/components/editor/NodeTreePanel.vue` | 树面板：搜索 / review 过滤·计数·导航 / 新增 / γ 浮动条 / 行列表 / 拖拽接线 | 创建 |
| `src/views/procedures/NodeEditorView.vue` | 隔离壳：load + 取程序 meta(name/code) + top bar(back/undo/autosave) + 两栏布局 | 创建 |
| `src/views/procedures/ProcedureEditorView.vue` | 加 flag gate（`?editor=node` → `<NodeEditorView>`，否则现状） | 修改（最小） |
| `tests/unit/...` | 各文件 vitest | 创建 |

---

## Task 1: store `batchSetKind` + 放宽 `buildSelection` 行类型

**Files:**
- Modify: `src/store/nodeEditor.ts`
- Modify: `src/utils/batchMark.ts`
- Test: `tests/unit/store/nodeEditor.spec.ts`（追加）、`tests/unit/utils/batchMark.spec.ts`（追加）

- [ ] **Step 1: 写失败测试（store）**

Append to `tests/unit/store/nodeEditor.spec.ts`:

```typescript
describe('nodeEditor store — batchSetKind', () => {
  it('batchSetKind sends kind for each id and replaces nodes with the full list', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>a</p>' }), n({ id: 'b', sort_order: 1000, body: '<p>b</p>' })])
    batchSpy.mockResolvedValue([n({ id: 'a', kind: 'step' }), n({ id: 'b', kind: 'step', sort_order: 1000 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.batchSetKind(['a', 'b'], 'step')
    expect(batchSpy).toHaveBeenCalledWith('p1', { a: { kind: 'step' }, b: { kind: 'step' } })
    expect(store.nodeMap.get('a')?.kind).toBe('step')
  })

  it('batchSetKind on empty ids is a no-op', async () => {
    listSpy.mockResolvedValue([n({ id: 'a' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.batchSetKind([], 'step')
    expect(batchSpy).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: 写失败测试（batchMark 放宽）**

Append to `tests/unit/utils/batchMark.spec.ts`:

```typescript
import { buildSelection } from '@/utils/batchMark'

describe('buildSelection — node rows (kind node|step)', () => {
  it('selects node-kind rows (no chapter skip) and supports shift range within same parent', () => {
    const rows = [
      { id: 'a', parent_id: 'p', kind: 'node' },
      { id: 'b', parent_id: 'p', kind: 'step' },
      { id: 'c', parent_id: 'p', kind: 'node' },
    ]
    const first = buildSelection({ current: new Set(), anchor: null, rows, rowId: 'a', shift: false })
    expect([...first.selection]).toEqual(['a'])
    const range = buildSelection({ current: first.selection, anchor: 'a', rows, rowId: 'c', shift: true })
    expect([...range.selection].sort()).toEqual(['a', 'b', 'c'])
  })
})
```

- [ ] **Step 3: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/store/nodeEditor.spec.ts tests/unit/utils/batchMark.spec.ts`
Expected: FAIL — `batchSetKind` 未定义；buildSelection 对 `kind:'node'` 行类型不接受（TS）或 import 报错。

- [ ] **Step 4: 实现（store）**

In `src/store/nodeEditor.ts`, add this action to the `actions` block right after `batchSetLevel`:

```typescript
    async batchSetKind(ids: string[], kind: 'node' | 'step'): Promise<void> {
      if (!this.procedureId || ids.length === 0) return
      const prev = new Map(ids.map((i) => [i, this.nodeMap.get(i)?.kind ?? 'node']))
      const updates: Record<string, { kind: 'node' | 'step' }> = {}
      for (const i of ids) updates[i] = { kind }
      this.nodes = await api.batchUpdateNodes(this.procedureId, updates)
      this._pushUndo(async () => {
        for (const [i, k] of prev) await this.setKind(i, k)
      })
    },
```

- [ ] **Step 5: 实现（batchMark 放宽）**

In `src/utils/batchMark.ts`: replace the `FlatRow` import + `buildSelection` signature so it takes a structural row type (keeps the `kind === 'chapter'` skip inert for node kinds). Replace:

```typescript
import type { FlatRow } from '@/types/node'
```

with:

```typescript
// 结构型行：只需 id / 父 / kind（kind 用 string，兼容旧 'chapter'|'content'|'step' 与新 'node'|'step'）。
export interface SelectableRow {
  id: string
  parent_id: string | null
  kind: string
}
```

and change the `rows` param type in `buildSelection` from `rows: FlatRow[]` to `rows: readonly SelectableRow[]` (signature only; body unchanged).

- [ ] **Step 6: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/store/nodeEditor.spec.ts tests/unit/utils/batchMark.spec.ts`
Expected: PASS（含既有用例；旧 `FlatRow[]` 仍可赋给 `SelectableRow[]`）。

- [ ] **Step 7: Commit**

```bash
git add src/store/nodeEditor.ts src/utils/batchMark.ts tests/unit/store/nodeEditor.spec.ts tests/unit/utils/batchMark.spec.ts
git commit -m "feat(fe/nodeEditor): batchSetKind + widen buildSelection to structural rows (B3a-2)"
```

---

## Task 2: `utils/nodeTreeDnd.ts` — 子树感知重排

**Files:**
- Create: `src/utils/nodeTreeDnd.ts`
- Test: `tests/unit/utils/nodeTreeDnd.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `tests/unit/utils/nodeTreeDnd.spec.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { computeReorder } from '@/utils/nodeTreeDnd'

// depth 表达派生层级：a(0) 下挂 b(1)/c(1)，d(0) 独立。
const nodes = [
  { id: 'a', depth: 0 },
  { id: 'b', depth: 1 },
  { id: 'c', depth: 1 },
  { id: 'd', depth: 0 },
]

describe('computeReorder', () => {
  it('moves a leaf after a sibling', () => {
    expect(computeReorder(nodes, 'b', 'c', 'after')).toEqual(['a', 'c', 'b', 'd'])
  })
  it('moves a leaf before a sibling', () => {
    expect(computeReorder(nodes, 'c', 'b', 'before')).toEqual(['a', 'c', 'b', 'd'])
  })
  it('drags a heading and carries its whole subtree as a block', () => {
    expect(computeReorder(nodes, 'a', 'd', 'after')).toEqual(['d', 'a', 'b', 'c'])
  })
  it('drags a heading before another heading (subtree intact)', () => {
    expect(computeReorder(nodes, 'd', 'a', 'before')).toEqual(['d', 'a', 'b', 'c'])
  })
  it('dropping onto own descendant is a no-op', () => {
    expect(computeReorder(nodes, 'a', 'b', 'after')).toEqual(['a', 'b', 'c', 'd'])
  })
  it('unknown drag/target id returns the original order', () => {
    expect(computeReorder(nodes, 'zz', 'a', 'after')).toEqual(['a', 'b', 'c', 'd'])
    expect(computeReorder(nodes, 'a', 'zz', 'after')).toEqual(['a', 'b', 'c', 'd'])
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/utils/nodeTreeDnd.spec.ts`
Expected: FAIL — `@/utils/nodeTreeDnd` 不存在。

- [ ] **Step 3: 实现**

Create `src/utils/nodeTreeDnd.ts`:

```typescript
import type { Node } from '@/types/node'

export type DropPosition = 'before' | 'after'

/** 子树感知重排：把 dragId（及其后 depth 更大的连续后代）整体移到 targetId 的 before/after，
 * 返回该程序全部节点的新 id 排列（喂给 store.reorder）。
 * 落点落在被拖块内部（拖到自己/后代）→ 原样返回（no-op）。
 * nodes 假定按 sort_order 升序、depth 为派生层级。 */
export function computeReorder(
  nodes: Pick<Node, 'id' | 'depth'>[],
  dragId: string,
  targetId: string,
  position: DropPosition,
): string[] {
  const ids = nodes.map((n) => n.id)
  const start = nodes.findIndex((n) => n.id === dragId)
  if (start < 0) return ids
  const dragDepth = nodes[start].depth
  let end = start
  while (end + 1 < nodes.length && nodes[end + 1].depth > dragDepth) end++
  const block = ids.slice(start, end + 1)
  const blockSet = new Set(block)
  if (blockSet.has(targetId)) return ids // 落在被拖块内 → no-op
  const rest = ids.filter((id) => !blockSet.has(id))
  const ti = rest.indexOf(targetId)
  if (ti < 0) return ids
  rest.splice(position === 'before' ? ti : ti + 1, 0, ...block)
  return rest
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/utils/nodeTreeDnd.spec.ts`
Expected: PASS（6）。

- [ ] **Step 5: Commit**

```bash
git add src/utils/nodeTreeDnd.ts tests/unit/utils/nodeTreeDnd.spec.ts
git commit -m "feat(fe/nodeTreeDnd): subtree-aware computeReorder for node drag (B3a-2)"
```

---

## Task 3: `NodeDetailPanel.vue` — 选中节点详情

**Files:**
- Create: `src/components/editor/NodeDetailPanel.vue`
- Test: `tests/unit/NodeDetailPanel.spec.ts`

镜像 `StepDetailPanel.vue` 的表单/附件结构，但消费 `nodeEditor` store、按统一模型写（body→`updateBody`、表单+附件→`updateForm`、level/kind/skip→`setLevel/setKind/toggleSkip`、review→`confirmReview`）。重型子组件（RichTextEditor/StepFormFields/FormFieldPreview）在单测里 stub。

- [ ] **Step 1: 写失败测试**

Create `tests/unit/NodeDetailPanel.spec.ts`:

```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import NodeDetailPanel from '@/components/editor/NodeDetailPanel.vue'
import { useNodeEditorStore } from '@/store/nodeEditor'
import type { Node } from '@/types/node'

function n(over: Partial<Node>): Node {
  return {
    id: 'x', procedure_id: 'p1', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

const stubs = {
  RichTextEditor: { template: '<div class="rte-stub" />', props: ['modelValue'], emits: ['update:modelValue'] },
  StepFormFields: { template: '<div class="sff-stub" />', props: ['schema', 'readonly'], emits: ['update:schema'] },
  FormFieldPreview: { template: '<div class="ffp-stub" />', props: ['schema'] },
}

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useNodeEditorStore()
  const w = mount(NodeDetailPanel, { global: { plugins: [ElementPlus, pinia], stubs }, attachTo: document.body })
  return { w, store }
}

beforeEach(() => vi.useRealTimers())

describe('NodeDetailPanel', () => {
  it('shows empty hint when nothing selected', () => {
    const { w } = mountPanel()
    expect(w.findComponent({ name: 'ElEmpty' }).exists()).toBe(true)
  })

  it('body edit (debounced) calls updateBody', async () => {
    vi.useFakeTimers()
    const { w, store } = mountPanel()
    store.nodes = [n({ id: 'a', body: '<p>old</p>' })]
    store.selectedId = 'a'
    const spy = vi.spyOn(store, 'updateBody').mockResolvedValue()
    await w.vm.$nextTick()
    w.findComponent({ name: 'RichTextEditor' }).vm.$emit('update:modelValue', '<p>new</p>')
    vi.advanceTimersByTime(600)
    expect(spy).toHaveBeenCalledWith('a', '<p>new</p>')
  })

  it('level select calls setLevel', async () => {
    const { w, store } = mountPanel()
    store.nodes = [n({ id: 'a', heading_level: null })]
    store.selectedId = 'a'
    const spy = vi.spyOn(store, 'setLevel').mockResolvedValue()
    await w.vm.$nextTick()
    w.findComponent({ name: 'ElSelect' }).vm.$emit('change', 2)
    expect(spy).toHaveBeenCalledWith('a', 2)
  })

  it('kind switch calls setKind', async () => {
    const { w, store } = mountPanel()
    store.nodes = [n({ id: 'a', kind: 'node' })]
    store.selectedId = 'a'
    const spy = vi.spyOn(store, 'setKind').mockResolvedValue()
    await w.vm.$nextTick()
    w.find('.kind-switch').findComponent({ name: 'ElSwitch' }).vm.$emit('change', true)
    expect(spy).toHaveBeenCalledWith('a', 'step')
  })

  it('step node renders form + attachment editor; adding a mark calls updateForm', async () => {
    const { w, store } = mountPanel()
    store.nodes = [n({ id: 'a', kind: 'step', input_schema: { type: 'CHECK' } })]
    store.selectedId = 'a'
    const spy = vi.spyOn(store, 'updateForm').mockResolvedValue()
    await w.vm.$nextTick()
    expect(w.find('.sff-stub').exists()).toBe(true)
    await w.find('.add-mark').trigger('click')
    expect(spy).toHaveBeenCalledWith('a', { type: 'CHECK' }, [{ filename: '', kind: 'document', note: '' }])
  })

  it('review node shows confirm button → confirmReview', async () => {
    const { w, store } = mountPanel()
    store.nodes = [n({ id: 'a', mark_status: 'review' })]
    store.selectedId = 'a'
    const spy = vi.spyOn(store, 'confirmReview').mockResolvedValue()
    await w.vm.$nextTick()
    await w.find('.confirm-review').trigger('click')
    expect(spy).toHaveBeenCalledWith('a')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/NodeDetailPanel.spec.ts`
Expected: FAIL — 组件不存在。

- [ ] **Step 3: 实现**

Create `src/components/editor/NodeDetailPanel.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useDebounceFn } from '@vueuse/core'
import RichTextEditor from './RichTextEditor.vue'
import StepFormFields from './StepFormFields.vue'
import FormFieldPreview from './FormFieldPreview.vue'
import { useNodeEditorStore } from '@/store/nodeEditor'
import { FORM_TYPE_META, isAlertType, isRichTextType } from '@/utils/editor'
import { FORM_TYPES } from '@/types/node'
import type { AttachmentMark, FormType, InputSchema } from '@/types/node'

// 统一节点详情（B3a-2）。即时·乐观写：body→updateBody（防抖）、表单+附件→updateForm。
const store = useNodeEditorStore()
const node = computed(() => store.selectedNode)
const procId = computed(() => store.procedureId ?? undefined)

const LEVELS = [
  { value: null as number | null, label: '正文' },
  { value: 1, label: '一级章节' },
  { value: 2, label: '二级章节' },
  { value: 3, label: '三级章节' },
]
const ATTACH_KINDS = [
  { value: 'video', label: '视频' },
  { value: 'image', label: '图片' },
  { value: 'document', label: '文档' },
  { value: 'audio', label: '音频' },
  { value: 'other', label: '其他' },
]

// step 节点的 input_schema 若为空 {} → 显示默认 COMMON，首次编辑时持久化。
const schema = computed<InputSchema>(() => {
  const s = node.value?.input_schema as InputSchema | Record<string, never>
  return s && 'type' in s ? (s as InputSchema) : { type: 'COMMON' }
})
const marks = computed<AttachmentMark[]>(() => node.value?.attachment_marks ?? [])

const pushBody = useDebounceFn((v: string) => {
  if (node.value) void store.updateBody(node.value.id, v)
}, 500)

function onLevel(v: number | null): void {
  if (node.value) void store.setLevel(node.value.id, v)
}
function onKindSwitch(isStep: boolean): void {
  if (node.value) void store.setKind(node.value.id, isStep ? 'step' : 'node')
}
function onSkip(): void {
  if (node.value) void store.toggleSkip(node.value.id)
}
function saveForm(nextSchema: InputSchema, nextMarks: AttachmentMark[]): void {
  if (node.value) void store.updateForm(node.value.id, nextSchema, nextMarks)
}
function onSchema(next: InputSchema): void {
  saveForm(next, marks.value)
}
function addMark(): void {
  saveForm(schema.value, [...marks.value, { filename: '', kind: 'document', note: '' }])
}
function updMark(i: number, patch: Partial<AttachmentMark>): void {
  saveForm(schema.value, marks.value.map((m, idx) => (idx === i ? { ...m, ...patch } : m)))
}
function removeMark(i: number): void {
  saveForm(schema.value, marks.value.filter((_, idx) => idx !== i))
}

function hasConfig(s: InputSchema): boolean {
  return Object.keys(s).some((k) => k !== 'type')
}
async function onTypeChange(next: FormType): Promise<void> {
  const cur = schema.value
  if (cur.type !== next && !isRichTextType(cur.type) && cur.type !== 'NONE' && hasConfig(cur)) {
    try {
      await ElMessageBox.confirm('切换类型会清空当前类型的配置（单位/范围/选项等），是否继续？', '切换确认', { type: 'warning' })
    } catch {
      return
    }
  }
  saveForm({ type: next }, marks.value)
}

const alertClass = computed(() => (isAlertType(schema.value.type) ? `alert-${schema.value.type.toLowerCase()}` : ''))
</script>

<template>
  <div v-if="node" class="node-detail">
    <el-form label-position="top">
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

    <el-collapse :model-value="['body', 'form', 'attach']">
      <el-collapse-item title="正文" name="body">
        <RichTextEditor
          :key="`body-${node.id}`"
          :model-value="node.body"
          variant="full"
          :procedure-id="procId"
          placeholder="输入正文…（首个块级元素文本作为标题）"
          @update:model-value="pushBody"
        />
      </el-collapse-item>

      <el-collapse-item v-if="node.kind === 'step'" title="执行表单" name="form">
        <el-form label-position="top">
          <el-form-item label="类型">
            <el-select :model-value="schema.type" @change="onTypeChange">
              <el-option v-for="t in FORM_TYPES" :key="t" :value="t" :label="FORM_TYPE_META[t].label" />
            </el-select>
          </el-form-item>
          <div v-if="isRichTextType(schema.type)" class="rt-wrap" :class="alertClass">
            <span class="rt-hint">富文本类型的提示文本随正文渲染；此处仅配置类型样式。</span>
          </div>
          <template v-else>
            <div class="config-preview">
              <div class="cp-config"><StepFormFields :schema="schema" :readonly="false" @update:schema="onSchema" /></div>
              <div class="cp-preview"><FormFieldPreview :schema="schema" /></div>
            </div>
          </template>
        </el-form>
      </el-collapse-item>

      <el-collapse-item v-if="node.kind === 'step'" title="附件标记" name="attach">
        <div v-for="(m, i) in marks" :key="i" class="mark-row">
          <el-input :model-value="m.filename" placeholder="文件名" @input="(v: string) => updMark(i, { filename: v })" />
          <el-select :model-value="m.kind" class="mark-kind" @change="(v: string) => updMark(i, { kind: v })">
            <el-option v-for="k in ATTACH_KINDS" :key="k.value" :value="k.value" :label="k.label" />
          </el-select>
          <el-input :model-value="m.note" placeholder="备注" @input="(v: string) => updMark(i, { note: v })" />
          <el-button size="small" text @click="removeMark(i)">✕</el-button>
        </div>
        <el-button class="add-mark" size="small" @click="addMark">+ 附件标记</el-button>
      </el-collapse-item>
    </el-collapse>

    <div v-if="node.mark_status === 'review'" class="review-bar">
      <span class="review-tag">待确认</span>
      <el-button class="confirm-review" size="small" type="primary" @click="store.confirmReview(node.id)">确认</el-button>
    </div>
  </div>
  <el-empty v-else description="选择左侧节点进行编辑" />
</template>

<style scoped>
.node-detail { padding: 8px 0 40px; }
.inline { display: flex; gap: 16px; }
.config-preview { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 8px; }
.cp-config, .cp-preview { flex: 1 1 280px; min-width: 0; }
.rt-wrap { padding-left: 8px; border-left: 3px solid transparent; }
.alert-note { border-left-color: var(--el-color-primary, #d97757); }
.alert-caution { border-left-color: #e6a23c; }
.alert-warning { border-left-color: #f56c6c; }
.rt-hint { font-size: 12px; color: #909399; }
.mark-row { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; }
.mark-kind { width: 120px; flex: none; }
.review-bar { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
.review-tag { font-size: 12px; color: #b88230; background: #fdf6ec; border: 1px solid #f5dab1; border-radius: 3px; padding: 1px 6px; }
</style>
```

注：`el-select` 的 `value` 用 `l.value as number` 是为兼容 `null`（正文）——EP option value 接受任意，运行时 `null` 正确回传给 `onLevel`，TS 经 `as number` 收口；`onLevel` 形参为 `number | null`。

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/NodeDetailPanel.spec.ts`
Expected: PASS（6）。

- [ ] **Step 5: Commit**

```bash
git add src/components/editor/NodeDetailPanel.vue tests/unit/NodeDetailPanel.spec.ts
git commit -m "feat(fe/NodeDetailPanel): node detail (body/level/kind/skip/form/attach/review) (B3a-2)"
```

---

## Task 4: `NodeTreeRow.vue` — 单行

**Files:**
- Create: `src/components/editor/NodeTreeRow.vue`
- Test: `tests/unit/NodeTreeRow.spec.ts`

行只展示 + 派发意图（store 调用在 NodeTreePanel）。chip 用 el-dropdown（jsdom 不渲染 popper，按 [[el-dropdown-jsdom-test]] 测 `@command` 经组件 `$emit`）。

- [ ] **Step 1: 写失败测试**

Create `tests/unit/NodeTreeRow.spec.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import NodeTreeRow from '@/components/editor/NodeTreeRow.vue'
import type { TreeRow } from '@/utils/nodeTree'
import type { Node } from '@/types/node'

function node(over: Partial<Node>): Node {
  return {
    id: 'a', procedure_id: 'p', sort_order: 0, heading_level: 1, kind: 'node',
    body: '<p>章节</p>', code: '1', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}
function treeRow(over: Partial<Node> = {}, row: Partial<TreeRow> = {}): TreeRow {
  const nd = node(over)
  return { node: nd, title: '章节', hasChildren: false, expanded: true, ...row }
}

const baseProps = { selected: false, selectedForMark: false, dropHint: '' as const }
function mountRow(row: TreeRow, extra: Record<string, unknown> = {}) {
  return mount(NodeTreeRow, {
    props: { row, ...baseProps, ...extra },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

describe('NodeTreeRow', () => {
  it('renders code + title', () => {
    const w = mountRow(treeRow({}, { title: '安全须知' }))
    expect(w.text()).toContain('1')
    expect(w.text()).toContain('安全须知')
  })

  it('indents by node.depth (depth 2 → paddingLeft 38px)', () => {
    const w = mountRow(treeRow({ depth: 2 }))
    expect((w.find('.ntr').element as HTMLElement).style.paddingLeft).toBe('38px')
  })

  it('click emits select; caret emits toggle', async () => {
    const w = mountRow(treeRow({}, { hasChildren: true }))
    await w.find('.ntr').trigger('click')
    expect(w.emitted('select')).toBeTruthy()
    await w.find('.ntr-caret').trigger('click')
    expect(w.emitted('toggle')).toBeTruthy()
  })

  it('chip dropdown command l2 emits chip("l2"); step emits chip("step")', async () => {
    const w = mountRow(treeRow())
    const dd = w.findComponent({ name: 'ElDropdown' })
    dd.vm.$emit('command', 'l2')
    dd.vm.$emit('command', 'step')
    expect(w.emitted('chip')).toEqual([['l2'], ['step']])
  })

  it('delete button emits remove', async () => {
    const w = mountRow(treeRow())
    await w.find('.ntr-del').trigger('click')
    expect(w.emitted('remove')).toBeTruthy()
  })

  it('checkbox emits check with shift flag', async () => {
    const w = mountRow(treeRow())
    await w.find('.ntr-check').trigger('click')
    expect(w.emitted('check')).toBeTruthy()
  })

  it('review node renders 待确认 badge', () => {
    const w = mountRow(treeRow({ mark_status: 'review' }))
    expect(w.find('.ntr-review').exists()).toBe(true)
  })

  it('dragstart/dragover/drop/dragend are forwarded', async () => {
    const w = mountRow(treeRow())
    await w.find('.ntr').trigger('dragstart')
    await w.find('.ntr').trigger('dragover')
    await w.find('.ntr').trigger('drop')
    await w.find('.ntr').trigger('dragend')
    expect(w.emitted('dragstart')).toBeTruthy()
    expect(w.emitted('dragover')).toBeTruthy()
    expect(w.emitted('drop')).toBeTruthy()
    expect(w.emitted('dragend')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/NodeTreeRow.spec.ts`
Expected: FAIL — 组件不存在。

- [ ] **Step 3: 实现**

Create `src/components/editor/NodeTreeRow.vue`:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { TreeRow } from '@/utils/nodeTree'

// 单个节点行（B3a-2）。仅展示 + 派发意图。chip command：l0(正文)/l1/l2/l3/step/node。
interface Props {
  row: TreeRow
  selected: boolean
  selectedForMark: boolean
  dropHint: '' | 'before' | 'after'
}
const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'select'): void
  (e: 'toggle'): void
  (e: 'check', shift: boolean): void
  (e: 'chip', command: string): void
  (e: 'remove'): void
  (e: 'dragstart', ev: DragEvent): void
  (e: 'dragover', ev: DragEvent): void
  (e: 'drop', ev: DragEvent): void
  (e: 'dragend'): void
}>()

const n = computed(() => props.row.node)
const levelLabel = computed(() => {
  const h = n.value.heading_level
  const base = h === null ? '正文' : `L${h}`
  return n.value.kind === 'step' ? `${base}·步骤` : base
})
</script>

<template>
  <div
    class="ntr"
    :class="[{ 'ntr--selected': selected }, dropHint ? `ntr--drop-${dropHint}` : '']"
    :style="{ boxSizing: 'border-box', paddingLeft: `${n.depth * 16 + 6}px` }"
    draggable="true"
    @click="emit('select')"
    @dragstart="emit('dragstart', $event)"
    @dragover.prevent="emit('dragover', $event)"
    @drop.prevent="emit('drop', $event)"
    @dragend="emit('dragend')"
  >
    <span class="ntr-caret" :class="{ 'ntr-caret--hidden': !row.hasChildren }" @click.stop="emit('toggle')">
      {{ row.expanded ? '▾' : '▸' }}
    </span>
    <el-checkbox
      :model-value="selectedForMark"
      class="ntr-check"
      @click.stop="emit('check', ($event as MouseEvent).shiftKey)"
    />
    <span class="ntr-actions" @click.stop>
      <el-dropdown trigger="click" :persistent="false" @command="(c: string) => emit('chip', c)">
        <el-button size="small" text class="ntr-chip">{{ levelLabel }} ▾</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="l0">正文</el-dropdown-item>
            <el-dropdown-item command="l1">一级章节</el-dropdown-item>
            <el-dropdown-item command="l2">二级章节</el-dropdown-item>
            <el-dropdown-item command="l3">三级章节</el-dropdown-item>
            <el-dropdown-item command="step" divided>设为步骤</el-dropdown-item>
            <el-dropdown-item command="node">取消步骤</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </span>
    <span class="ntr-code">{{ n.code }}</span>
    <span class="ntr-title">{{ row.title }}</span>
    <span v-if="n.mark_status === 'review'" class="ntr-review" title="解析存疑，待确认">待确认</span>
    <el-button class="ntr-del" size="small" text title="删除" @click.stop="emit('remove')">✕</el-button>
  </div>
</template>

<style scoped>
.ntr { display: flex; align-items: center; gap: 4px; height: 30px; font-size: 13px; cursor: pointer; padding-right: 6px; white-space: nowrap; border-bottom: 1px solid transparent; }
.ntr:hover { background: var(--el-fill-color-light, #f5f7fa); }
.ntr--selected { background: var(--el-color-primary-light-9, #fbf1ee); }
.ntr--drop-before { box-shadow: inset 0 2px 0 var(--el-color-primary, #d97757); }
.ntr--drop-after { box-shadow: inset 0 -2px 0 var(--el-color-primary, #d97757); }
.ntr-caret { width: 14px; text-align: center; color: #999; flex: none; }
.ntr-caret--hidden { visibility: hidden; }
.ntr-check { flex: none; }
.ntr-actions { flex: none; }
.ntr-chip { font-variant-numeric: tabular-nums; }
.ntr-code { color: #888; font-variant-numeric: tabular-nums; flex: none; }
.ntr-title { overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; }
.ntr-review { flex: none; font-size: 11px; line-height: 1; padding: 1px 4px; border-radius: 3px; color: #b88230; background: #fdf6ec; border: 1px solid #f5dab1; }
.ntr-del { flex: none; display: none; }
.ntr:hover .ntr-del { display: inline-flex; }
</style>
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/NodeTreeRow.spec.ts`
Expected: PASS（8）。

- [ ] **Step 5: Commit**

```bash
git add src/components/editor/NodeTreeRow.vue tests/unit/NodeTreeRow.spec.ts
git commit -m "feat(fe/NodeTreeRow): single node row with level chip + drag + review badge (B3a-2)"
```

---

## Task 5: `NodeTreePanel.vue` — 树面板

**Files:**
- Create: `src/components/editor/NodeTreePanel.vue`
- Test: `tests/unit/NodeTreePanel.spec.ts`

消费 `nodeEditor` store：渲染 `store.rows`、搜索、review 过滤/计数/导航、新增、γ 多选浮动条、行事件接线、子树拖拽（`computeReorder` → `reorder`）。多选用 `buildSelection`（Task 1 放宽后接受 node 行）。

- [ ] **Step 1: 写失败测试**

Create `tests/unit/NodeTreePanel.spec.ts`:

```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import NodeTreePanel from '@/components/editor/NodeTreePanel.vue'
import { useNodeEditorStore } from '@/store/nodeEditor'
import type { Node } from '@/types/node'

function n(over: Partial<Node>): Node {
  return {
    id: 'x', procedure_id: 'p1', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

function setup(nodes: Node[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useNodeEditorStore()
  store.procedureId = 'p1'
  store.nodes = nodes
  store.selectedId = nodes[0]?.id ?? null
  const w = mount(NodeTreePanel, { global: { plugins: [ElementPlus, pinia] }, attachTo: document.body })
  return { w, store }
}

beforeEach(() => vi.restoreAllMocks())

describe('NodeTreePanel', () => {
  it('renders one NodeTreeRow per visible row', () => {
    const { w } = setup([
      n({ id: 'a', heading_level: 1, body: '<p>A</p>' }),
      n({ id: 'b', parent_id: 'a', depth: 1, sort_order: 1000, body: '<p>B</p>' }),
    ])
    expect(w.findAllComponents({ name: 'NodeTreeRow' })).toHaveLength(2)
  })

  it('row chip "l2" calls setLevel; "step" calls setKind', async () => {
    const { w, store } = setup([n({ id: 'a', heading_level: 1, body: '<p>A</p>' })])
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    const setKind = vi.spyOn(store, 'setKind').mockResolvedValue()
    const row = w.findComponent({ name: 'NodeTreeRow' })
    row.vm.$emit('chip', 'l2')
    row.vm.$emit('chip', 'step')
    expect(setLevel).toHaveBeenCalledWith('a', 2)
    expect(setKind).toHaveBeenCalledWith('a', 'step')
  })

  it('row chip "l0" sets level null (正文)', async () => {
    const { w, store } = setup([n({ id: 'a', heading_level: 2, body: '<p>A</p>' })])
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    w.findComponent({ name: 'NodeTreeRow' }).vm.$emit('chip', 'l0')
    expect(setLevel).toHaveBeenCalledWith('a', null)
  })

  it('row remove calls removeNode; select calls select', async () => {
    const { w, store } = setup([n({ id: 'a', body: '<p>A</p>' })])
    const remove = vi.spyOn(store, 'removeNode').mockResolvedValue()
    const row = w.findComponent({ name: 'NodeTreeRow' })
    row.vm.$emit('select')
    row.vm.$emit('remove')
    expect(store.selectedId).toBe('a')
    expect(remove).toHaveBeenCalledWith('a')
  })

  it('add button calls createNode (正文/普通)', async () => {
    const { w, store } = setup([n({ id: 'a', body: '<p>A</p>' })])
    const create = vi.spyOn(store, 'createNode').mockResolvedValue()
    await w.find('.np-add').trigger('click')
    expect(create).toHaveBeenCalledWith({ heading_level: null, kind: 'node' })
  })

  it('check builds selection; floating bar 设为L1 calls batchSetLevel then clears selection', async () => {
    const { w, store } = setup([
      n({ id: 'a', body: '<p>A</p>' }),
      n({ id: 'b', sort_order: 1000, body: '<p>B</p>' }),
    ])
    const batch = vi.spyOn(store, 'batchSetLevel').mockResolvedValue()
    const rows = w.findAllComponents({ name: 'NodeTreeRow' })
    rows[0].vm.$emit('check', false)
    rows[1].vm.$emit('check', false)
    await w.vm.$nextTick()
    expect(store.selection.size).toBe(2)
    await w.find('.np-bar-l1').trigger('click')
    expect(batch).toHaveBeenCalledWith(['a', 'b'], 1)
    expect(store.selection.size).toBe(0)
  })

  it('review filter toggle flips store.reviewOnly; count shown', async () => {
    const { w, store } = setup([
      n({ id: 'a', body: '<p>A</p>', mark_status: 'review' }),
      n({ id: 'b', sort_order: 1000, body: '<p>B</p>' }),
    ])
    expect(w.find('.np-review-count').text()).toContain('1')
    await w.find('.np-review-toggle').trigger('click')
    expect(store.reviewOnly).toBe(true)
  })

  it('drop reorders via computeReorder → store.reorder', async () => {
    const { w, store } = setup([
      n({ id: 'a', body: '<p>A</p>' }),
      n({ id: 'b', sort_order: 1000, body: '<p>B</p>' }),
    ])
    const reorder = vi.spyOn(store, 'reorder').mockResolvedValue()
    const rows = w.findAllComponents({ name: 'NodeTreeRow' })
    rows[0].vm.$emit('dragstart', new Event('dragstart'))
    rows[1].vm.$emit('drop', new Event('drop'))
    expect(reorder).toHaveBeenCalledWith(['b', 'a'])
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/NodeTreePanel.spec.ts`
Expected: FAIL — 组件不存在。

- [ ] **Step 3: 实现**

Create `src/components/editor/NodeTreePanel.vue`:

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import NodeTreeRow from './NodeTreeRow.vue'
import { useNodeEditorStore } from '@/store/nodeEditor'
import { buildSelection } from '@/utils/batchMark'
import { nextReviewId } from '@/utils/reviewNav'
import { computeReorder, type DropPosition } from '@/utils/nodeTreeDnd'
import type { TreeRow } from '@/utils/nodeTree'

const store = useNodeEditorStore()
const anchor = ref<string | null>(null)
const dragId = ref<string | null>(null)
const dropOnId = ref<string | null>(null)
const dropPos = ref<DropPosition>('before')

const search = computed({ get: () => store.search, set: (v: string) => (store.search = v) })

function onSelect(id: string): void {
  store.select(id)
}
function onChip(id: string, command: string): void {
  if (command === 'l0') void store.setLevel(id, null)
  else if (command === 'l1') void store.setLevel(id, 1)
  else if (command === 'l2') void store.setLevel(id, 2)
  else if (command === 'l3') void store.setLevel(id, 3)
  else if (command === 'step') void store.setKind(id, 'step')
  else if (command === 'node') void store.setKind(id, 'node')
}
function onCheck(id: string, shift: boolean): void {
  const rows = store.rows.map((r) => ({ id: r.node.id, parent_id: r.node.parent_id, kind: r.node.kind }))
  const res = buildSelection({ current: store.selection, anchor: anchor.value, rows, rowId: id, shift })
  store.selection = res.selection
  anchor.value = res.anchor
  for (const wmsg of res.warnings) ElMessage.warning(wmsg)
}
function addNode(): void {
  void store.createNode({ heading_level: null, kind: 'node' })
}
function gotoNextReview(): void {
  const id = nextReviewId(
    store.rows.map((r) => ({ id: r.node.id, mark_status: r.node.mark_status })),
    store.selectedId,
  )
  if (id) store.select(id)
}

// γ 浮动条
const selectedIds = computed(() => [...store.selection])
function clearSel(): void {
  store.selection = new Set()
  anchor.value = null
}
async function barLevel(level: number | null): Promise<void> {
  await store.batchSetLevel(selectedIds.value, level)
  clearSel()
}
async function barStep(): Promise<void> {
  await store.batchSetKind(selectedIds.value, 'step')
  clearSel()
}

// 拖拽
function onDragStart(id: string): void {
  dragId.value = id
}
function onDragOver(id: string, ev: DragEvent): void {
  const el = ev.currentTarget as HTMLElement | null
  if (!el) return
  const rect = el.getBoundingClientRect()
  dropOnId.value = id
  dropPos.value = ev.clientY - rect.top < rect.height / 2 ? 'before' : 'after'
}
function onDrop(id: string): void {
  if (dragId.value && dragId.value !== id) {
    // 仅当 dragover 命中同一行时用算出的 before/after，否则默认 after（含未模拟 dragover 的单测）。
    const pos: DropPosition = dropOnId.value === id ? dropPos.value : 'after'
    const ordered = computeReorder(store.nodes, dragId.value, id, pos)
    void store.reorder(ordered)
  }
  onDragEnd()
}
function onDragEnd(): void {
  dragId.value = null
  dropOnId.value = null
}
function hintFor(row: TreeRow): '' | 'before' | 'after' {
  return dropOnId.value === row.node.id ? dropPos.value : ''
}
</script>

<template>
  <div class="node-tree">
    <div class="np-toolbar">
      <el-input v-model="search" class="np-search" size="small" placeholder="搜索标题…" clearable />
      <el-button class="np-add" size="small" @click="addNode">＋ 新增节点</el-button>
      <span class="np-review-count">待确认 {{ store.reviewCount }}</span>
      <el-button
        class="np-review-toggle"
        size="small"
        :type="store.reviewOnly ? 'primary' : 'default'"
        @click="store.reviewOnly = !store.reviewOnly"
      >
        仅看待确认
      </el-button>
      <el-button class="np-review-next" size="small" :disabled="!store.reviewCount" @click="gotoNextReview">下一个</el-button>
    </div>

    <div v-if="store.selection.size" class="np-bar">
      <span>已选 {{ store.selection.size }}</span>
      <el-button class="np-bar-text" size="small" @click="barLevel(null)">设为正文</el-button>
      <el-button class="np-bar-l1" size="small" @click="barLevel(1)">设为 L1</el-button>
      <el-button class="np-bar-l2" size="small" @click="barLevel(2)">设为 L2</el-button>
      <el-button class="np-bar-l3" size="small" @click="barLevel(3)">设为 L3</el-button>
      <el-button class="np-bar-step" size="small" @click="barStep">设为步骤</el-button>
      <el-button size="small" text @click="clearSel">清空选择</el-button>
    </div>

    <div class="np-rows">
      <NodeTreeRow
        v-for="row in store.rows"
        :key="row.node.id"
        :row="row"
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
      <el-empty v-if="!store.rows.length" description="暂无节点" />
    </div>
  </div>
</template>

<style scoped>
.node-tree { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.np-toolbar { display: flex; align-items: center; gap: 8px; padding: 8px; flex-wrap: wrap; border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5); }
.np-search { width: 180px; }
.np-review-count { font-size: 12px; color: #b88230; }
.np-bar { display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: var(--el-color-primary-light-9, #fbf1ee); flex-wrap: wrap; }
.np-rows { flex: 1; overflow-y: auto; min-height: 0; }
</style>
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/NodeTreePanel.spec.ts`
Expected: PASS（8）。

- [ ] **Step 5: Commit**

```bash
git add src/components/editor/NodeTreePanel.vue tests/unit/NodeTreePanel.spec.ts
git commit -m "feat(fe/NodeTreePanel): tree panel (chip/multiselect/review/search/create/drag) (B3a-2)"
```

---

## Task 6: `NodeEditorView.vue` + `ProcedureEditorView` flag gate

**Files:**
- Create: `src/views/procedures/NodeEditorView.vue`
- Modify: `src/views/procedures/ProcedureEditorView.vue`
- Test: `tests/unit/NodeEditorView.spec.ts`

NodeEditorView：隔离壳，onMounted `nodeEditor.load(id)` + 取程序 meta（`fetchProcedureDetail` 仅用 `name`/`code` 显示，display-only）；top bar：back / undo（`undo`+`canUndo`）/ autosave 指示（`$onAction` 计数）。两栏：NodeTreePanel + NodeDetailPanel。

- [ ] **Step 1: 写失败测试**

Create `tests/unit/NodeEditorView.spec.ts`:

```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ElementPlus from 'element-plus'

const { loadSpy, undoSpy } = vi.hoisted(() => ({ loadSpy: vi.fn(), undoSpy: vi.fn() }))
vi.mock('@/api/procedures', () => ({
  fetchProcedureDetail: vi.fn().mockResolvedValue({ id: 'p1', name: '示例程序', code: 'SOP-001' }),
}))

import NodeEditorView from '@/views/procedures/NodeEditorView.vue'
import { useNodeEditorStore } from '@/store/nodeEditor'

const stubs = { NodeTreePanel: { template: '<div class="tree-stub" />' }, NodeDetailPanel: { template: '<div class="detail-stub" />' } }

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useNodeEditorStore()
  vi.spyOn(store, 'load').mockImplementation(async (id: string) => { loadSpy(id); store.procedureId = id })
  vi.spyOn(store, 'undo').mockImplementation(async () => { undoSpy() })
  const w = mount(NodeEditorView, { props: { procedureId: 'p1' }, global: { plugins: [ElementPlus, pinia], stubs } })
  return { w, store }
}

beforeEach(() => vi.clearAllMocks())

describe('NodeEditorView', () => {
  it('loads nodes on mount and fetches procedure meta (name shown)', async () => {
    const { w } = mountView()
    await flushPromises()
    expect(loadSpy).toHaveBeenCalledWith('p1')
    expect(w.text()).toContain('示例程序')
  })

  it('mounts tree + detail panels', async () => {
    const { w } = mountView()
    await flushPromises()
    expect(w.find('.tree-stub').exists()).toBe(true)
    expect(w.find('.detail-stub').exists()).toBe(true)
  })

  it('undo button disabled until canUndo, then calls store.undo', async () => {
    const { w, store } = mountView()
    await flushPromises()
    const btn = w.find('.nev-undo')
    expect(btn.attributes('disabled')).toBeDefined()
    store.undoStack = [async () => {}]
    await w.vm.$nextTick()
    expect(w.find('.nev-undo').attributes('disabled')).toBeUndefined()
    await w.find('.nev-undo').trigger('click')
    expect(undoSpy).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/NodeEditorView.spec.ts`
Expected: FAIL — 组件不存在。

- [ ] **Step 3: 实现（NodeEditorView）**

Create `src/views/procedures/NodeEditorView.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import NodeTreePanel from '@/components/editor/NodeTreePanel.vue'
import NodeDetailPanel from '@/components/editor/NodeDetailPanel.vue'
import { useNodeEditorStore } from '@/store/nodeEditor'
import { fetchProcedureDetail } from '@/api/procedures'

// 隔离的统一节点编辑器（B3a-2，behind ?editor=node）。即时·乐观写，无 Save。
const props = defineProps<{ procedureId: string }>()
const router = useRouter()
const store = useNodeEditorStore()

const title = ref('')
const code = ref('')
const inflight = ref(0)
const saving = ref(false)

// autosave 指示：经 $onAction 计数 mutating actions（不改 store）。
const MUTATING = new Set([
  'setLevel', 'setKind', 'toggleSkip', 'batchSetLevel', 'batchSetKind',
  'confirmReview', 'createNode', 'removeNode', 'reorder', 'updateBody', 'updateForm', 'undo',
])
store.$onAction(({ name, after, onError }) => {
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

onMounted(async () => {
  await store.load(props.procedureId)
  try {
    const meta = await fetchProcedureDetail(props.procedureId)
    title.value = meta.name
    code.value = meta.code
  } catch {
    /* meta 仅作面包屑，失败不阻塞编辑 */
  }
})

function goBack(): void {
  void router.push({ name: 'procedure-library' })
}
</script>

<template>
  <div class="node-editor">
    <div class="nev-bar">
      <el-button class="nev-back" size="small" text @click="goBack">← 返回</el-button>
      <span class="nev-title">{{ code }} {{ title }}</span>
      <el-button class="nev-undo" size="small" :disabled="!store.canUndo" @click="store.undo()">↶ 撤销</el-button>
      <span class="nev-save" :class="{ 'is-saving': saving }">{{ saving ? '保存中…' : '✓ 已保存' }}</span>
    </div>
    <div class="nev-body">
      <div class="nev-left"><NodeTreePanel /></div>
      <div class="nev-right"><NodeDetailPanel /></div>
    </div>
  </div>
</template>

<style scoped>
.node-editor { display: flex; flex-direction: column; height: calc(100vh - 0px); min-height: 480px; }
.nev-bar { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5); }
.nev-title { font-weight: 600; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nev-save { font-size: 12px; color: #67c23a; }
.nev-save.is-saving { color: #909399; }
.nev-body { flex: 1; display: flex; min-height: 0; }
.nev-left { flex: 1; min-width: 280px; min-height: 0; }
.nev-right { width: 380px; min-width: 320px; border-left: 1px solid var(--el-border-color-lighter, #ebeef5); overflow-y: auto; padding: 0 14px; }
</style>
```

- [ ] **Step 4: 运行确认通过（NodeEditorView）**

Run: `cd frontend && npx vitest run tests/unit/NodeEditorView.spec.ts`
Expected: PASS（3）。

- [ ] **Step 5: 实现 flag gate（ProcedureEditorView）**

In `src/views/procedures/ProcedureEditorView.vue`:

(a) Add the import + computed in `<script setup>` (after `const id = computed(...)`):

```typescript
import NodeEditorView from '@/views/procedures/NodeEditorView.vue'
const nodeMode = computed(() => route.query.editor === 'node')
```

(b) In `onMounted`, early-return before loading the legacy store — make the very first line of the `onMounted(async () => {` body:

```typescript
  if (nodeMode.value) return
```

(c) In `<template>`, wrap the existing root. Change the outer element from:

```vue
  <div v-loading="store.loading" class="editor">
```

to gate it — insert the node editor as a sibling before it and add `v-else`:

```vue
  <NodeEditorView v-if="nodeMode" :procedure-id="id" />
  <div v-else v-loading="store.loading" class="editor">
```

(The existing `</div>` closing the `.editor` block stays; everything inside is unchanged.)

- [ ] **Step 6: 运行确认通过（gate 不回归既有）**

Run: `cd frontend && npx vitest run` （全量；既有 ProcedureEditor 相关 spec 仍绿，新 6 文件绿）
Expected: 全绿（既有 410 + 本期新增）。

- [ ] **Step 7: Commit**

```bash
git add src/views/procedures/NodeEditorView.vue src/views/procedures/ProcedureEditorView.vue tests/unit/NodeEditorView.spec.ts
git commit -m "feat(fe/NodeEditorView): isolated node editor shell + ?editor=node gate (B3a-2)"
```

---

## Task 7: 全量回归 + 类型 + lint + 手动 dev 验收

**Files:** 无新增

- [ ] **Step 1: 全部前端测试**

Run: `cd frontend && npx vitest run`
Expected: 既有全绿 + 本期新增（batchMark +1、nodeEditor store +2、nodeTreeDnd 6、NodeDetailPanel 6、NodeTreeRow 8、NodeTreePanel 8、NodeEditorView 3）全绿。记录总数。

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无新增类型错误。

- [ ] **Step 3: Lint**

Run: `cd frontend && npx eslint src/store/nodeEditor.ts src/utils/batchMark.ts src/utils/nodeTreeDnd.ts "src/components/editor/NodeTree*.vue" src/components/editor/NodeDetailPanel.vue "src/views/procedures/Node*.vue" src/views/procedures/ProcedureEditorView.vue --max-warnings 0`
Expected: 0 warning/error。

- [ ] **Step 4: 手动 dev 验收（running-smartsop-dev + chrome-devtools）**

启动 dev（后端 8000 / 前端 5173，见 `running-smartsop-dev`），浏览器开 `/procedures/<某程序id>/edit?editor=node`：
- 验证：节点树渲染、行 chip 改 level/kind 实时生效、新增/删除、拖拽换位（标题带子树）、多选浮动条批量改 level、review 徽章 + 确认、详情 body 编辑落库、step 表单/附件、撤销、autosave 指示「保存中…/已保存」。
- 验证旧编辑器不受影响：开同一程序 `/edit`（无 flag）仍是旧 UI、行为不变。
- 记录验收结果（截图/要点）。

- [ ] **Step 5: Commit（若有修正）**

```bash
git add -A
git commit -m "chore(fe): type/lint/regression fixes for B3a-2"
```

---

## 完成标准（B3a-2）

1. `?editor=node` 下 `ProcedureEditorView` 渲染隔离的 `NodeEditorView`，旧编辑器零行为变化、零代码改动（除一处 gate）。
2. 节点树（`NodeTreePanel`+`NodeTreeRow`）：渲染 `store.rows`、行 chip → `setLevel/setKind`、多选 + γ 浮动条 → `batchSetLevel/batchSetKind`、review 徽章·过滤·导航、搜索、新增、删除、子树感知拖拽 → `reorder`。
3. 详情（`NodeDetailPanel`）：body → `updateBody`（防抖）、level/kind/skip chip、step 表单 + attachment → `updateForm`、review 确认 → `confirmReview`。
4. autosave 指示经 `$onAction`；撤销经 `undo`/`canUndo`。
5. 全 vitest 绿、`vue-tsc` 干净、新文件 eslint 干净；手动 dev 验收通过；app 默认行为不变。

## 交接 B3b 的事实
- 切换默认路由（去 flag）+ 删旧：`ChapterTreePanel`/`TreeRow`/旧详情面板/`layerMark`/标记模式 UI/`save_procedure`/`applyLayerRoles`；把 `review`/`batchMark`（删 `kind==='chapter'` skip——现已是结构型行，可顺势收口）正式迁入新树。
- 延后项（本期未做，spec 已列）：虚拟列表、级联多选、β 键盘、δ markdown、redo、发布/版本/PDF chrome、跨标签 412 精修。
- `buildSelection` 已放宽为 `SelectableRow`（id/parent_id/kind:string）；node 行直接可用。
