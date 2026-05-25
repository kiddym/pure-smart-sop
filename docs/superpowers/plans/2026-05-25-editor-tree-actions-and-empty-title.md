# 编辑器树行操作精简 + 空标题定位 + PDF 预览 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 精简程序树章节行操作（＋新增▾/↑/↓/⋮）、移除树层级升降级、把空标题章节做成可定位、并在编辑器加 PDF 预览入口。

**Architecture:** 纯前端改动（Vue 3 + Pinia + Element Plus）。复用既有「待确认」导航范式（`reviewNav` + 工具条）实现「缺标题」定位；复用既有 `PdfPreviewDialog`。无后端 / schema 改动。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript、Pinia、Element Plus、Vitest + @vue/test-utils。

设计来源：`docs/superpowers/specs/2026-05-25-editor-tree-actions-and-empty-title-design.md`

**任务顺序约束**（避免中间态报错）：先做加法（util / store 新增）与组件改写，**最后**才删除已无引用的 store 升降级方法。Task 5、6 必须早于 Task 7。

---

## 文件结构

| 文件 | 职责 / 改动 |
| --- | --- |
| `frontend/src/utils/reviewNav.ts` | 抽出通用 `nextRowId(rows, currentId, predicate)`；`nextReviewId` 复用它 |
| `frontend/src/store/procedureEditor.ts` | `addChapterNode`/`addStepNode` 支持 `afterId` 同级定位；`missingTitleCount` getter + `expandAncestors` action；删除 promote/demote |
| `frontend/src/components/editor/TreeRow.vue` | 动作区改写为 ＋新增▾/↑/↓/⋮（三种行统一）；移除 promote/demote props+emits；空标题行标记 |
| `frontend/src/components/editor/ChapterTreePanel.vue` | `addTargetFor` + `onAddFromRow` 同级/子节点语义；缺标题定位条 + 过滤 + 导航；移除 promote/demote 绑定 |
| `frontend/src/composables/useEditorKeyboard.ts` | 移除 `Tab`/`Shift+Tab` 分支与 `onPromote`/`onDemote` |
| `frontend/src/views/procedures/ProcedureEditorView.vue` | 移除 promote/demote handler；保存拦截定位首个缺标题；PDF 预览挂载 + dirty 保存流程 |
| `frontend/src/components/editor/ChapterDetailPanel.vue` | 空标题章节标题框挂载自动聚焦 |
| `frontend/src/components/editor/EditorTopBar.vue` | 可编辑时新增「PDF 预览」按钮（emit `preview-pdf`） |

测试命令：所有测试 `cd frontend && npm run test`；单个文件 `cd frontend && npx vitest run tests/unit/<file>`。

---

## Task 1: `reviewNav` 抽出通用 `nextRowId`

**Files:**
- Modify: `frontend/src/utils/reviewNav.ts`
- Test: `frontend/tests/unit/utils/reviewNav.spec.ts`

- [ ] **Step 1: 追加 `nextRowId` 的失败测试**

在 `frontend/tests/unit/utils/reviewNav.spec.ts` 顶部 import 改为：

```ts
import { describe, it, expect } from 'vitest'
import { nextReviewId, nextRowId } from '@/utils/reviewNav'
```

在文件末尾（最后一个 `})` 之后）追加：

```ts
describe('nextRowId（通用谓词导航）', () => {
  const rows = [
    { id: 'a', kind: 'chapter', title: '有标题' },
    { id: 'b', kind: 'chapter', title: '' },
    { id: 'c', kind: 'content', title: '' }, // 内容块空标题不应命中 chapter 谓词
    { id: 'd', kind: 'chapter', title: '   ' }, // 纯空白视为空
  ]
  const isMissing = (r: { kind: string; title: string }) => r.kind === 'chapter' && !r.title.trim()

  it('无选中 → 第一个命中', () => {
    expect(nextRowId(rows, null, isMissing)).toBe('b')
  })
  it('从某命中 → 下一个命中（跳过非命中、环绕）', () => {
    expect(nextRowId(rows, 'b', isMissing)).toBe('d')
  })
  it('最后一个命中 → 环绕回第一个', () => {
    expect(nextRowId(rows, 'd', isMissing)).toBe('b')
  })
  it('无命中 → null', () => {
    expect(nextRowId(rows, null, () => false)).toBeNull()
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/utils/reviewNav.spec.ts`
Expected: FAIL —「nextRowId is not a function」/ 导入报错。

- [ ] **Step 3: 实现 `nextRowId` 并让 `nextReviewId` 复用**

把 `frontend/src/utils/reviewNav.ts` 整体替换为：

```ts
interface ReviewRow {
  id: string
  mark_status: string
}

/**
 * 文档序里 currentId 之后第一个满足 predicate 的行 id（环绕）。
 * currentId 为 null 或不在 rows 中 → 取第一个命中。无命中 → null。
 */
export function nextRowId<T extends { id: string }>(
  rows: T[],
  currentId: string | null,
  predicate: (r: T) => boolean,
): string | null {
  const hits = rows.filter(predicate)
  if (hits.length === 0) return null
  if (currentId === null) return hits[0].id
  const curIdx = rows.findIndex((r) => r.id === currentId)
  if (curIdx === -1) return hits[0].id
  for (let i = 1; i <= rows.length; i++) {
    const r = rows[(curIdx + i) % rows.length]
    if (predicate(r)) return r.id
  }
  return hits[0].id
}

/**
 * 文档序里 currentId 之后的下一个 review 行 id（环绕）。无 review → null。
 */
export function nextReviewId(rows: ReviewRow[], currentId: string | null): string | null {
  return nextRowId(rows, currentId, (r) => r.mark_status === 'review')
}
```

- [ ] **Step 4: 运行确认通过（含旧用例回归）**

Run: `cd frontend && npx vitest run tests/unit/utils/reviewNav.spec.ts`
Expected: PASS（旧 `nextReviewId` 5 例 + 新 `nextRowId` 4 例全绿）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/reviewNav.ts frontend/tests/unit/utils/reviewNav.spec.ts
git commit -m "refactor(editor): generalize reviewNav into nextRowId(predicate)"
```

---

## Task 2: store — `addChapterNode`/`addStepNode` 支持 `afterId` 同级定位

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts`（`addChapterNode` ≈ 524、`addStepNode` ≈ 544）
- Test: `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/tests/unit/procedureEditorStore.spec.ts` 的 `describe('新增节点', ...)` 块内追加两个用例：

```ts
  it('addChapterNode 带 afterId：插到该兄弟之后并重排 sort_order', () => {
    const s = seed() // 根级已有 a(0), b(1)
    const id = s.addChapterNode(null, 'chapter', 'a') // 期望落在 a 与 b 之间
    const order = s.chapters
      .filter((c) => c.parent_id === null)
      .sort((x, y) => x.sort_order - y.sort_order)
      .map((c) => c.id)
    expect(order).toEqual(['a', id, 'b'])
  })

  it('addStepNode 带 afterId：在同章节内插到该步骤之后', () => {
    const s = seed()
    s.steps = [stp('s1', 'a', 0), stp('s2', 'a', 1)]
    const id = s.addStepNode('a', 's1') // 期望落在 s1 与 s2 之间
    const order = s.steps
      .filter((st) => st.chapter_id === 'a')
      .sort((x, y) => x.sort_order - y.sort_order)
      .map((st) => st.id)
    expect(order).toEqual(['s1', id, 's2'])
  })
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts`
Expected: FAIL — 多传的第三个参数被忽略，新节点落在末尾（order 末位是新 id）。

- [ ] **Step 3: 实现 `afterId` 参数**

在 `frontend/src/store/procedureEditor.ts` 把 `addChapterNode` 改为（新增 `afterId` 形参与定位逻辑）：

```ts
    addChapterNode(parentId: string | null, contentType: ContentType, afterId: string | null = null): string {
      this.pushUndo()
      const siblings = this.chapters.filter((c) => c.parent_id === parentId)
      const node: EditorChapter = {
        id: genTempId(),
        parent_id: parentId,
        content_type: contentType,
        title: '',
        rich_content: '',
        skip_numbering: false,
        mark_status: 'unmarked',
        sort_order: this.nextSortOrder(siblings),
      }
      this.chapters.push(node)
      this.dirtyChapters.add(node.id)
      if (afterId) {
        const after = this.chapterMap.get(afterId)
        if (after && after.parent_id === parentId) {
          for (const c of this.chapters) {
            if (c.parent_id === parentId && c.id !== node.id && c.sort_order > after.sort_order) {
              c.sort_order += 1
              this.dirtyChapters.add(c.id)
            }
          }
          node.sort_order = after.sort_order + 1
        }
      }
      if (parentId) this.setExpanded(parentId, true)
      this.selectedId = node.id
      return node.id
    },
```

把 `addStepNode` 改为：

```ts
    addStepNode(chapterId: string | null, afterId: string | null = null): string {
      this.pushUndo()
      const siblings = this.steps.filter((s) => s.chapter_id === chapterId)
      const node = emptyStep(chapterId, this.nextSortOrder(siblings))
      this.steps.push(node)
      this.dirtySteps.add(node.id)
      if (afterId) {
        const after = this.stepMap.get(afterId)
        if (after && after.chapter_id === chapterId) {
          for (const st of this.steps) {
            if (st.chapter_id === chapterId && st.id !== node.id && st.sort_order > after.sort_order) {
              st.sort_order += 1
              this.dirtySteps.add(st.id)
            }
          }
          node.sort_order = after.sort_order + 1
        }
      }
      if (chapterId) this.setExpanded(chapterId, true)
      this.selectedId = node.id
      return node.id
    },
```

- [ ] **Step 4: 运行确认通过（含旧新增用例回归）**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts`
Expected: PASS（旧「addChapterNode 建临时节点」「addStepNode 追加」仍绿，因 `afterId` 默认 null）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "feat(editor): addChapterNode/addStepNode accept afterId for sibling insert"
```

---

## Task 3: store — `missingTitleCount` getter + `expandAncestors` action

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts`（getters 区 + actions 区）
- Test: `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/tests/unit/procedureEditorStore.spec.ts` 末尾追加：

```ts
describe('缺标题 + 展开祖先', () => {
  it('missingTitleCount 只统计标题为空的「章节」（不含内容块/步骤）', () => {
    setActivePinia(createPinia())
    const s = useProcedureEditorStore()
    s.procedure = meta()
    const empty = chap('e', null, 0)
    empty.title = '   ' // 纯空白
    const content = chap('ct', null, 1)
    content.content_type = 'content'
    content.title = '' // 内容块空标题不计入
    s.chapters = [chap('a', null, 2), empty, content]
    s.steps = [stp('s', 'a', 0)] // s 的 title 由 stp() 设为 's'
    expect(s.missingTitleCount).toBe(1)
  })

  it('expandAncestors 展开目标的全部祖先', () => {
    setActivePinia(createPinia())
    const s = useProcedureEditorStore()
    s.procedure = meta()
    s.chapters = [chap('g', null, 0), chap('p', 'g', 0), chap('c', 'p', 0)]
    s.expanded = {}
    s.expandAncestors('c')
    expect(s.expanded.p).toBe(true)
    expect(s.expanded.g).toBe(true)
    expect(s.expanded.c ?? false).toBe(false) // 只展开祖先，不含自身
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts`
Expected: FAIL —「missingTitleCount is not ...」/「expandAncestors is not a function」。

- [ ] **Step 3: 实现 getter 与 action**

在 `frontend/src/store/procedureEditor.ts` 的 **getters** 区（与 `addButtonStateFor` 同级，紧随其后）加入：

```ts
    missingTitleCount(state): number {
      return state.chapters.filter((c) => c.content_type === 'chapter' && !c.title.trim()).length
    },
```

在 **actions** 区（与 `setExpanded`/`toggleExpanded` 邻近）加入：

```ts
    // 展开 id 的全部祖先（不含自身），用于把目标滚入可见。
    expandAncestors(id: string): void {
      let pid = this.chapterMap.get(id)?.parent_id ?? this.stepMap.get(id)?.chapter_id ?? null
      while (pid) {
        this.setExpanded(pid, true)
        pid = this.chapterMap.get(pid)?.parent_id ?? null
      }
    },
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "feat(editor): missingTitleCount getter + expandAncestors action"
```

---

## Task 4: `TreeRow.vue` — 动作区改写 + 移除升降级 + 缺标题标记

**Files:**
- Modify: `frontend/src/components/editor/TreeRow.vue`
- Test: `frontend/tests/unit/TreeRow.spec.ts`

- [ ] **Step 1: 改写测试以匹配新设计（先让其失败）**

把 `frontend/tests/unit/TreeRow.spec.ts` 整体替换为：

```ts
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import TreeRow from '@/components/editor/TreeRow.vue'
import type { FlatRow } from '@/types/node'

function row(overrides: Partial<FlatRow> = {}): FlatRow {
  return {
    id: 'a',
    kind: 'chapter',
    depth: 0,
    parent_id: null,
    title: '安全须知',
    code: '1.0',
    skip_numbering: false,
    mark_status: 'unmarked',
    form_type: null,
    has_children: false,
    expanded: false,
    fallback: '(未命名章节)',
    ...overrides,
  }
}

const baseProps = {
  selected: false,
  markMode: false,
  selectedForMark: false,
  addState: { canAddChapter: true, canAddContent: true, canAddStep: true },
  editable: true,
  canMoveUp: false,
  canMoveDown: false,
  dropHint: '' as const,
}

function mountRow(r: FlatRow, extra: Record<string, unknown> = {}) {
  return mount(TreeRow, {
    props: { row: r, ...baseProps, ...extra },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

describe('TreeRow', () => {
  it('显示 code 与标题', () => {
    const w = mountRow(row())
    expect(w.text()).toContain('1.0')
    expect(w.text()).toContain('安全须知')
  })

  it('uses border-box sizing so virtual row height stays at 30px', () => {
    const w = mountRow(row())
    expect(getComputedStyle(w.find('.tr').element).boxSizing).toBe('border-box')
  })

  it('点击行派发 select', async () => {
    const w = mountRow(row())
    await w.find('.tr').trigger('click')
    expect(w.emitted('select')).toBeTruthy()
  })

  it('三种行都渲染「＋新增」触发器', () => {
    for (const kind of ['chapter', 'content', 'step'] as const) {
      const w = mountRow(row({ id: kind, kind, code: '1.1' }))
      expect(w.text()).toContain('＋新增')
    }
  })

  it('不再渲染升级/降级符号', () => {
    const w = mountRow(row())
    expect(w.text()).not.toContain('⇤')
    expect(w.text()).not.toContain('⇥')
  })

  it('空标题「章节」显示「缺标题」标记，内容块不显示', () => {
    const wc = mountRow(row({ title: '' }))
    expect(wc.find('.tr-missing-tag').exists()).toBe(true)
    expect(wc.find('.tr--missing').exists()).toBe(true)

    const wct = mountRow(row({ id: 'x', kind: 'content', title: '', fallback: '(空内容)' }))
    expect(wct.find('.tr-missing-tag').exists()).toBe(false)
  })

  it('⋮ 菜单点「删除」派发 remove', async () => {
    const w = mountRow(row())
    // 打开 ⋮ 下拉（trigger=click），菜单 teleport 到 body
    await w.find('.more-trigger').trigger('click')
    const items = Array.from(document.querySelectorAll('.el-dropdown-menu__item')) as HTMLElement[]
    const del = items.find((el) => el.textContent?.includes('删除'))
    expect(del).toBeTruthy()
    del!.click()
    expect(w.emitted('remove')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/TreeRow.spec.ts`
Expected: FAIL —「＋新增」「.tr-missing-tag」「.more-trigger」尚不存在；旧 `canPromote`/`canDemote` 已从 baseProps 移除。

- [ ] **Step 3: 改写 `TreeRow.vue`**

`<script setup>` 区：把 `Props` 接口删掉 `canPromote`/`canDemote` 两行；把 `emit` 定义里删掉 `(e: 'promote')` 与 `(e: 'demote')` 两行；在 `display`/`titleFallback` 附近新增：

```ts
const missingTitle = computed(() => props.row.kind === 'chapter' && !props.row.title.trim())
```

模板：把整段 `<span v-if="editable && !markMode" class="tr-actions" ...>…</span>`（现有 +章/+容/+步/⇤/⇥/↑/↓/✕）替换为：

```html
    <span v-if="missingTitle" class="tr-missing-tag" title="章节标题为空">缺标题</span>

    <span v-if="editable && !markMode" class="tr-actions" @click.stop>
      <el-dropdown
        v-if="addState.canAddChapter || addState.canAddContent || addState.canAddStep"
        trigger="click"
        @command="(c: 'chapter' | 'content' | 'step') => emit('add', c)"
      >
        <el-button size="small" text class="add-trigger">＋新增 ▾</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item :disabled="!addState.canAddChapter" command="chapter">子章节</el-dropdown-item>
            <el-dropdown-item :disabled="!addState.canAddContent" command="content">内容块</el-dropdown-item>
            <el-dropdown-item :disabled="!addState.canAddStep" command="step">步骤</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-button size="small" text :disabled="!canMoveUp" title="上移" @click="emit('move', 'up')">↑</el-button>
      <el-button size="small" text :disabled="!canMoveDown" title="下移" @click="emit('move', 'down')">↓</el-button>
      <el-dropdown trigger="click" @command="() => emit('remove')">
        <el-button size="small" text class="more-trigger" title="更多">⋮</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="remove">删除</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </span>
```

> 注意：把「缺标题」标记 `<span class="tr-missing-tag">` 放在 `tr-actions` 之前、紧随 `tr-review`/`tr-typebar` 之后，保证标记常驻（不随 hover 显隐）。

模板根节点 class 绑定改为加入 `tr--missing`：

```html
    :class="[{ 'tr--selected': selected, 'tr--missing': missingTitle }, dropHint ? `tr--drop-${dropHint}` : '']"
```

`<style scoped>` 区追加：

```css
.tr--missing {
  box-shadow: inset 3px 0 0 var(--el-color-warning, #e6a23c);
  background: #fffaf2;
}
.tr-missing-tag {
  flex: none;
  font-size: 11px;
  line-height: 1;
  padding: 1px 5px;
  border-radius: 3px;
  color: #b88230;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
}
.tr-actions .el-dropdown {
  height: 100%;
  display: inline-flex;
  align-items: center;
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/TreeRow.spec.ts`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/editor/TreeRow.vue frontend/tests/unit/TreeRow.spec.ts
git commit -m "feat(editor): tree row actions => ＋新增▾/↑/↓/⋮; drop promote/demote; missing-title marker"
```

---

## Task 5: `ChapterTreePanel.vue` — 新增语义 + 缺标题定位条 + 移除升降级绑定

**Files:**
- Modify: `frontend/src/components/editor/ChapterTreePanel.vue`
- Test: `frontend/tests/unit/ChapterTreePanel.spec.ts`

- [ ] **Step 1: 写失败测试（新增语义 + 缺标题条）**

在 `frontend/tests/unit/ChapterTreePanel.spec.ts` 的 `describe('ChapterTreePanel', ...)` 块内追加。先在文件顶部 import 处补 `vi`：

```ts
import { describe, expect, it, vi } from 'vitest'
```

追加用例：

```ts
  it('章节行＋新增=加子节点；步骤行＋新增=同父级加同级', () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '章一', null, 0)]
    store.steps = [
      { id: 's1', chapter_id: 'c1', title: '步一', content: '', input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    store.expanded = { c1: true }
    const addChapterSpy = vi.spyOn(store, 'addChapterNode').mockReturnValue('tmp')
    const addStepSpy = vi.spyOn(store, 'addStepNode').mockReturnValue('tmp')

    const wrapper = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    const rows = wrapper.findAllComponents({ name: 'TreeRow' })
    const chapterRow = rows.find((r) => r.props('row').id === 'c1')!
    const stepRow = rows.find((r) => r.props('row').id === 's1')!

    chapterRow.vm.$emit('add', 'step')
    expect(addStepSpy).toHaveBeenCalledWith('c1', null) // 章节 → 加子节点

    stepRow.vm.$emit('add', 'step')
    expect(addStepSpy).toHaveBeenCalledWith('c1', 's1') // 步骤 → 同父级、该行之后
    expect(addChapterSpy).not.toHaveBeenCalled()
  })

  it('存在缺标题章节时显示定位条与计数', () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '', null, 0), chapter('c2', '有题', null, 1)]
    store.expanded = {}
    const wrapper = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    expect(wrapper.find('.missing-bar').exists()).toBe(true)
    expect(wrapper.find('.missing-bar').text()).toContain('1')
  })
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/ChapterTreePanel.spec.ts`
Expected: FAIL —「.missing-bar」不存在；`add` 事件仍按旧逻辑 `onAdd(row.id, kind)` 调用（步骤行会以 's1' 作为 parent 调用，断言不符）。

- [ ] **Step 3: 改写 `ChapterTreePanel.vue`**

import 行：把 `nextReviewId` 的导入改为同时引入 `nextRowId`：

```ts
import { nextReviewId, nextRowId } from '@/utils/reviewNav'
```

把现有 `addStateFor` / `onAdd` 替换为（保留供根级工具栏用的 `onAdd`，新增 `addTargetFor` 与 `onAddFromRow`）：

```ts
function addTargetFor(row: FlatRow): { parentId: string | null; afterId: string | null } {
  if (row.kind === 'chapter') return { parentId: row.id, afterId: null }
  return { parentId: row.parent_id, afterId: row.id }
}
function addStateFor(row: FlatRow) {
  return store.addButtonStateFor(addTargetFor(row).parentId)
}
function onAdd(parentId: string | null, kind: 'chapter' | 'content' | 'step'): void {
  if (kind === 'step') store.addStepNode(parentId)
  else store.addChapterNode(parentId, kind)
}
function onAddFromRow(row: FlatRow, kind: 'chapter' | 'content' | 'step'): void {
  const { parentId, afterId } = addTargetFor(row)
  if (kind === 'step') store.addStepNode(parentId, afterId)
  else store.addChapterNode(parentId, kind, afterId)
}
```

在 `reviewFilter` 邻近新增缺标题导航与过滤：

```ts
const missingFilter = ref(false)
function gotoNextMissing(): void {
  const id = nextRowId(store.flatRows, store.selectedId, (r) => r.kind === 'chapter' && !r.title.trim())
  if (id) store.selectNode(id)
}
```

`visibleRows` computed 内，在 `reviewFilter` 过滤之后、搜索过滤之前，加一行：

```ts
  if (missingFilter.value) rows = keepWithAncestors(rows, (r) => r.kind === 'chapter' && !r.title.trim())
```

模板工具栏：在 `review-bar` 那个 `<div>` 之后新增缺标题条：

```html
      <div v-if="store.editable && store.missingTitleCount" class="missing-bar">
        <span class="missing-count" title="章节标题为空">⚠ {{ store.missingTitleCount }} 个章节缺标题</span>
        <el-button size="small" @click="gotoNextMissing">下一个</el-button>
        <el-checkbox v-model="missingFilter" size="small">只看缺标题</el-checkbox>
      </div>
```

模板 `<TreeRow>` 绑定：删除 `:can-promote=...`、`:can-demote=...` 两行与 `@promote=...`、`@demote=...` 两行；把 `@add` 改为：

```html
          @add="(kind) => onAddFromRow(row, kind)"
```

`<style scoped>` 区追加（与 `.review-bar` 同款）：

```css
.missing-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.missing-count {
  font-size: 12px;
  color: #b8860b;
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/ChapterTreePanel.spec.ts`
Expected: PASS（含「renders rows」「虚拟窗口」旧用例）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/editor/ChapterTreePanel.vue frontend/tests/unit/ChapterTreePanel.spec.ts
git commit -m "feat(editor): leaf=sibling/chapter=child add semantics + missing-title locator bar"
```

---

## Task 6: `useEditorKeyboard` + `ProcedureEditorView` — 移除升降级键 + 保存定位首个缺标题

**Files:**
- Modify: `frontend/src/composables/useEditorKeyboard.ts`
- Modify: `frontend/src/views/procedures/ProcedureEditorView.vue`

> 本任务以编译/类型检查 + 全量测试作为验证（`useEditorKeyboard` 与 `ProcedureEditorView` 无既有单测、且涉及路由/持久化重型依赖，新建单测成本过高；保存定位行为在 Task 10 手动冒烟）。

- [ ] **Step 1: 删除 `useEditorKeyboard` 的升降级**

在 `frontend/src/composables/useEditorKeyboard.ts`：
- `Handlers` 接口删掉 `onPromote: () => void` 与 `onDemote: () => void` 两行。
- 删除整段 `Tab` 处理：

```ts
    if (e.key === 'Tab' && !isTyping(e.target)) {
      e.preventDefault()
      if (e.shiftKey) h.onPromote()
      else h.onDemote()
      return
    }
```

- [ ] **Step 2: 删除 `ProcedureEditorView` 的升降级 handler**

在 `frontend/src/views/procedures/ProcedureEditorView.vue` 的 `useEditorKeyboard({ ... })` 调用里，删除：

```ts
  onPromote: () => {
    const id = store.selectedId
    if (id && store.editable) void store.promoteChapter(id)
  },
  onDemote: () => {
    const id = store.selectedId
    if (id && store.editable) void store.demoteChapter(id)
  },
```

- [ ] **Step 3: 保存拦截时定位首个缺标题**

在 `frontend/src/views/procedures/ProcedureEditorView.vue` 的 `doSave` 中，把：

```ts
  const errors = store.validateForSave()
  if (errors.length) {
    ElMessage.error(`请先修复：${errors.join('；')}`)
    return
  }
```

替换为：

```ts
  const errors = store.validateForSave()
  if (errors.length) {
    const firstMissing = store.flatRows.find((r) => r.kind === 'chapter' && !r.title.trim())
    if (firstMissing) {
      store.expandAncestors(firstMissing.id)
      store.selectNode(firstMissing.id)
      ElMessage.error(`请先补全 ${store.missingTitleCount} 个章节标题，已定位到 ${firstMissing.code}`)
    } else {
      ElMessage.error(`请先修复：${errors.join('；')}`)
    }
    return
  }
```

- [ ] **Step 4: 类型检查 + 全量测试**

Run: `cd frontend && npm run typecheck && npm run test`
Expected: PASS（注意：此时 `store.promoteChapter`/`demoteChapter` 仍存在但已无引用，类型检查应通过）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/composables/useEditorKeyboard.ts frontend/src/views/procedures/ProcedureEditorView.vue
git commit -m "feat(editor): drop Tab/Shift+Tab indent; save locates first empty-title chapter"
```

---

## Task 7: store — 删除已无引用的 promote/demote 方法

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts`
- Test: `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: 写断言「已删除 / 仍保留」的测试**

在 `frontend/tests/unit/procedureEditorStore.spec.ts` 末尾追加：

```ts
describe('移除树层级 promote/demote（保留 promoteContentToChapter）', () => {
  it('promoteChapter/demoteChapter/canPromoteChapter/canDemoteChapter 不再存在', () => {
    setActivePinia(createPinia())
    const s = useProcedureEditorStore() as unknown as Record<string, unknown>
    expect(s.promoteChapter).toBeUndefined()
    expect(s.demoteChapter).toBeUndefined()
    expect(s.canPromoteChapter).toBeUndefined()
    expect(s.canDemoteChapter).toBeUndefined()
  })
  it('promoteContentToChapter 仍保留', () => {
    setActivePinia(createPinia())
    const s = useProcedureEditorStore()
    expect(typeof s.promoteContentToChapter).toBe('function')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts`
Expected: FAIL — 这四个方法当前仍定义（非 undefined）。

- [ ] **Step 3: 删除四个方法**

在 `frontend/src/store/procedureEditor.ts` 删除以下四个成员的完整定义（保留其余、尤其保留 `promoteContentToChapter`）：
- getter `canPromoteChapter(id)`（≈ 701）
- getter `canDemoteChapter(id)`（≈ 706）
- action `async promoteChapter(id)`（≈ 729）
- action `async demoteChapter(id)`（≈ 744）

> 删除后用 `grep -n "promoteChapter\|demoteChapter\|canPromoteChapter\|canDemoteChapter" frontend/src` 确认仅余无关注释（如 §774 处对 promote/demote 的文字说明可一并清理或保留）。

- [ ] **Step 4: 运行测试 + 类型检查**

Run: `cd frontend && npm run typecheck && npx vitest run tests/unit/procedureEditorStore.spec.ts`
Expected: PASS（无任何文件再引用被删方法）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "refactor(editor): remove tree-level promote/demote from store (keep promoteContentToChapter)"
```

---

## Task 8: `ChapterDetailPanel.vue` — 空标题章节自动聚焦标题框

**Files:**
- Modify: `frontend/src/components/editor/ChapterDetailPanel.vue`
- Test: `frontend/tests/unit/ChapterDetailPanel.spec.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/tests/unit/ChapterDetailPanel.spec.ts` 末尾追加（注意用 `attachTo: document.body` 才能检测焦点）：

```ts
describe('ChapterDetailPanel 空标题自动聚焦', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('选中标题为空的章节时，标题输入框自动获得焦点', async () => {
    const store = useProcedureEditorStore()
    // @ts-expect-error 最小 procedure
    store.procedure = { id: 'p1', version: 1, status: 'DRAFT', revision: 1, is_current: true }
    store.chapters = [{
      id: 'a', parent_id: null, content_type: 'chapter', title: '', rich_content: '',
      skip_numbering: false, mark_status: 'unmarked', sort_order: 0,
    }]
    store.steps = []
    store.selectedId = 'a'
    mount(ChapterDetailPanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    await new Promise((r) => setTimeout(r, 0))
    expect(document.activeElement?.tagName).toBe('TEXTAREA')
  })

  it('标题非空时不抢焦点', async () => {
    const store = useProcedureEditorStore()
    // @ts-expect-error 最小 procedure
    store.procedure = { id: 'p1', version: 1, status: 'DRAFT', revision: 1, is_current: true }
    store.chapters = [{
      id: 'a', parent_id: null, content_type: 'chapter', title: '已有标题', rich_content: '',
      skip_numbering: false, mark_status: 'unmarked', sort_order: 0,
    }]
    store.steps = []
    store.selectedId = 'a'
    mount(ChapterDetailPanel, { global: { plugins: [ElementPlus] }, attachTo: document.body })
    await new Promise((r) => setTimeout(r, 0))
    expect(document.activeElement?.tagName).not.toBe('TEXTAREA')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/ChapterDetailPanel.spec.ts`
Expected: FAIL — 标题框不会自动聚焦。

- [ ] **Step 3: 实现自动聚焦**

在 `frontend/src/components/editor/ChapterDetailPanel.vue`：
- `<script setup>` 顶部 import 改为 `import { computed, onMounted, ref } from 'vue'`。
- 在 `const ro = ...` 之后加入：

```ts
const titleRef = ref<{ focus: () => void } | null>(null)
onMounted(() => {
  if (chapter.value && !chapter.value.title.trim()) titleRef.value?.focus()
})
```

- 模板里给章节标题 `el-input` 加 `ref="titleRef"`：

```html
          <el-input
            ref="titleRef"
            :model-value="chapter.title"
            type="textarea"
            autosize
            maxlength="500"
            show-word-limit
            :disabled="ro"
            placeholder="输入章节标题"
            @input="onTitle"
          />
```

> 该面板在 `ProcedureEditorView` 以 `:key="store.selectedId"` 重建，故每次选中（含刚新增）的空标题章节都会触发 `onMounted` 聚焦。

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/ChapterDetailPanel.spec.ts`
Expected: PASS（含旧「接受待确认」用例）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/editor/ChapterDetailPanel.vue frontend/tests/unit/ChapterDetailPanel.spec.ts
git commit -m "feat(editor): autofocus chapter title input when empty"
```

---

## Task 9: PDF 预览入口（EditorTopBar 按钮 + 编辑器挂载弹框 + dirty 保存流程）

**Files:**
- Modify: `frontend/src/components/editor/EditorTopBar.vue`
- Modify: `frontend/src/views/procedures/ProcedureEditorView.vue`
- Test (new): `frontend/tests/unit/EditorTopBar.spec.ts`

- [ ] **Step 1: 为 EditorTopBar 写按钮失败测试（新建文件）**

新建 `frontend/tests/unit/EditorTopBar.spec.ts`：

```ts
import { describe, expect, it, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import EditorTopBar from '@/components/editor/EditorTopBar.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

function seedEditable() {
  const store = useProcedureEditorStore()
  // @ts-expect-error 最小 procedure（editable 需 is_current + DRAFT）
  store.procedure = {
    id: 'p1', code: 'QC-001', name: '测试', version: 1, is_current: true,
    status: 'DRAFT', folder_full_path: '', revision: 1,
  }
}

describe('EditorTopBar · PDF 预览按钮', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('可编辑时渲染「PDF 预览」并点按 emit preview-pdf', async () => {
    seedEditable()
    const w = mount(EditorTopBar, { global: { plugins: [ElementPlus] } })
    const btn = w.findAll('button').find((b) => b.text().includes('PDF 预览'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(w.emitted('preview-pdf')).toBeTruthy()
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/EditorTopBar.spec.ts`
Expected: FAIL —「PDF 预览」按钮不存在。

- [ ] **Step 3: EditorTopBar 加按钮**

在 `frontend/src/components/editor/EditorTopBar.vue`：
- `defineEmits` 追加一行 `(e: 'preview-pdf'): void`。
- 在 `<div v-if="store.editable" class="right">` 内，「标记模式」按钮之后、「保存」之前插入：

```html
      <el-button size="small" @click="emit('preview-pdf')">PDF 预览</el-button>
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/EditorTopBar.spec.ts`
Expected: PASS。

- [ ] **Step 5: ProcedureEditorView 挂载弹框 + dirty 流程**

在 `frontend/src/views/procedures/ProcedureEditorView.vue`：
- import 区加入：

```ts
import PdfPreviewDialog from '@/components/PdfPreview/PdfPreviewDialog.vue'
```

- 在 `const publishVisible = ref(false)` 邻近新增：

```ts
const pdfPreviewVisible = ref(false)
async function onPreviewPdf(): Promise<void> {
  if (store.isDirty) {
    try {
      await ElMessageBox.confirm('预览需要先保存当前修改，是否保存并预览？', 'PDF 预览', {
        confirmButtonText: '保存并预览',
        cancelButtonText: '取消',
        type: 'warning',
      })
    } catch {
      return
    }
    await doSave()
    if (store.isDirty) return // 保存失败（校验/冲突）→ 不打开
  }
  pdfPreviewVisible.value = true
}
```

- 模板 `<EditorTopBar ... />` 追加监听：

```html
        @preview-pdf="onPreviewPdf"
```

- 在 `<PublishChecklistDialog ... />` 邻近挂载（`store.procedure` 已在外层 `v-else-if` 保证存在）：

```html
      <PdfPreviewDialog v-model="pdfPreviewVisible" :procedure-id="store.procedure.id" />
```

- [ ] **Step 6: 类型检查 + 全量测试**

Run: `cd frontend && npm run typecheck && npm run test`
Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/components/editor/EditorTopBar.vue frontend/src/views/procedures/ProcedureEditorView.vue frontend/tests/unit/EditorTopBar.spec.ts
git commit -m "feat(editor): PDF preview button in topbar (save-then-preview when dirty)"
```

---

## Task 10: 全量校验 + 手动冒烟

**Files:** 无（验证任务）

- [ ] **Step 1: Lint + 类型检查 + 全量测试 + 构建**

Run:
```bash
cd frontend && npm run lint && npm run typecheck && npm run test && npm run build
```
Expected: 全部成功，0 error / 0 warning。

- [ ] **Step 2: 手动冒烟（用 `run` skill 启动应用，或 `cd frontend && npm run dev`）**

逐条确认：
1. 章节 / 内容块 / 步骤行 hover 时均显示 `＋新增 ▾ ↑ ↓ ⋮`，不再有 ⇤ ⇥。
2. 章节行 ＋新增 → 章/容/步：新节点进入该章节（子节点）。
3. 步骤行（位于多步骤章节中段）＋新增 → 步骤：新步骤出现在该行**正下方**（同级、紧随）。
4. 内容块行 ＋新增 → 内容块：新内容块紧随该行（同级）。
5. ⋮ → 删除 生效；↑ ↓ 上下移生效；拖拽改父级仍可用。
6. 按 `Tab`/`Shift+Tab` 不再缩进层级（无反应）。
7. 新增一个章节 → 标题框自动聚焦；该行显示「缺标题」+ 琥珀左边框；工具栏出现「⚠ N 个章节缺标题 · 下一个 · 只看缺标题」。
8. 「下一个」在缺标题章节间循环；「只看缺标题」过滤生效。
9. 仍有缺标题时点「保存」：被拦截、自动选中并展开到第一个缺标题章节、提示「请先补全 N 个章节标题，已定位到 …」。
10. 顶栏「PDF 预览」：无改动时直接打开弹框；有未保存改动时弹「保存并预览」确认，保存成功后打开。

- [ ] **Step 3: 完成**

确认 1–10 全绿后，本计划完成。如需合并/PR，使用 superpowers:finishing-a-development-branch。

---

## 自审记录（spec 覆盖 / 占位符 / 类型一致）

- **spec 覆盖**：话题1（Task 4+5）、话题2（Task 4/5/6/7）、话题3 行内标记+定位条+导航+保存拦截+方案C聚焦（Task 3/4/5/6/8）、话题4 PDF（Task 9，移动端执行页明确不做）。
- **占位符**：无 TBD/TODO；每个代码步骤含完整代码。
- **类型一致**：`nextRowId`（Task1）↔ ChapterTreePanel 调用（Task5）；`addChapterNode/addStepNode(afterId)`（Task2）↔ `onAddFromRow`（Task5）；`missingTitleCount`/`expandAncestors`（Task3）↔ ChapterTreePanel/ProcedureEditorView（Task5/6）；`preview-pdf` emit（Task9 EditorTopBar）↔ `@preview-pdf`（Task9 View）。
