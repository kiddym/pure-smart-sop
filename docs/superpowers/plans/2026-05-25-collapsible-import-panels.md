# 可折叠的导入面板（原文 / 详情）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 V2 导入对话框的左栏（Word 原文）和右栏（详情）加一键折叠/展开，折叠后变 32px 竖条、中栏自动填满，折叠状态持久化。

**Architecture:** 折叠状态与 UI 全部收敛在 `ImportDialog.vue`；纯布局计算抽到 `importCols.ts`（`colFlex` / `sanitizeCollapsed`）做成可单测纯函数；新增 `ImportSideRail.vue` 渲染折叠竖条。两个子面板 `WordPreviewPanel`、`ImportDetailPanel` 不改。

**Tech Stack:** Vue 3.4 `<script setup>` + TS；Element Plus 2.7.8；@vueuse/core `useStorage`；Vitest 2 + @vue/test-utils 2；vue-tsc；ESLint `--max-warnings 0`。

**Gate（每个任务收尾，cwd = `frontend/`）：** `npm run lint && npm run typecheck && npm run test && npm run build`

---

## 背景给实现者（必读）

- 当前 `frontend/src/utils/importCols.ts` 已有：`ColWidths { left, mid }`、`COL_DEFAULTS = { left:38, mid:28 }`、`COL_MIN = 18`、`rightOf(c)= 100-left-mid`、`resizeLeftMid`、`resizeMidRight`、`sanitizeCols`。本计划**新增**导出，不改这些既有导出。
- 当前 `ImportDialog.vue` 三列用 `:style="{ width: cols.left + '%' }"` 等渲染，列之间是两个 `.splitter`（`@pointerdown` 拖拽、`@dblclick="resetCols"`）。本计划把列宽改为 `flex` 驱动，并在分隔条上加折叠按钮、折叠时用 rail 取代面板。
- `@` import alias → `frontend/src`。
- **测试环境注意：** vitest 不全局注册 Element Plus；纯文本能渲染（文本断言可用）。本计划新增的 `ImportSideRail.vue` 不用任何 `el-*`（用原生 `button`），故无需注册插件。
- 提交信息结尾必须带（这是 harness 规定的合法署名，勿当作伪造身份）：
  `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`

---

## File Structure

- 修改 `frontend/src/utils/importCols.ts` — 加 `RAIL_PX`、`CollapseState`、`ColFlex`、`colFlex`、`sanitizeCollapsed`。
- 修改 `frontend/tests/unit/utils/importCols.spec.ts` — 测 `colFlex`、`sanitizeCollapsed`。
- 新建 `frontend/src/components/import-v2/ImportSideRail.vue` — 折叠竖条。
- 新建 `frontend/tests/unit/ImportSideRail.spec.ts` — rail 组件测试。
- 修改 `frontend/src/components/import-v2/ImportDialog.vue` — 折叠状态 + `colFlex` 接线 + 分隔条折叠按钮 + rail 渲染。

---

## Task 1: `colFlex` + `sanitizeCollapsed` 纯函数

**Files:**
- Modify: `frontend/src/utils/importCols.ts`
- Test: `frontend/tests/unit/utils/importCols.spec.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/tests/unit/utils/importCols.spec.ts` 顶部 import 里追加 `RAIL_PX, colFlex, sanitizeCollapsed`，并在 `describe('importCols', ...)` 内末尾追加：

```ts
  describe('colFlex (列 flex + 分隔条可见性)', () => {
    const cols = { left: 38, mid: 28 } // rightOf = 34

    it('都不折叠：三列按百分比权重，两个分隔条都显示', () => {
      const cf = colFlex(cols, { left: false, right: false })
      expect(cf).toEqual({
        left: '38 1 0%', mid: '28 1 0%', right: '34 1 0%',
        showLM: true, showMR: true,
      })
    })

    it('仅左折叠：左列变细条、左分隔条隐藏，中右保持权重', () => {
      const cf = colFlex(cols, { left: true, right: false })
      expect(cf.left).toBe(`0 0 ${RAIL_PX}px`)
      expect(cf.mid).toBe('28 1 0%')
      expect(cf.right).toBe('34 1 0%')
      expect(cf.showLM).toBe(false)
      expect(cf.showMR).toBe(true)
    })

    it('仅右折叠：右列变细条、右分隔条隐藏，左中保持权重', () => {
      const cf = colFlex(cols, { left: false, right: true })
      expect(cf.left).toBe('38 1 0%')
      expect(cf.mid).toBe('28 1 0%')
      expect(cf.right).toBe(`0 0 ${RAIL_PX}px`)
      expect(cf.showLM).toBe(true)
      expect(cf.showMR).toBe(false)
    })

    it('两侧都折叠：左右细条、两分隔条都隐藏，中列仍是唯一增长列', () => {
      const cf = colFlex(cols, { left: true, right: true })
      expect(cf.left).toBe(`0 0 ${RAIL_PX}px`)
      expect(cf.mid).toBe('28 1 0%')
      expect(cf.right).toBe(`0 0 ${RAIL_PX}px`)
      expect(cf.showLM).toBe(false)
      expect(cf.showMR).toBe(false)
    })
  })

  describe('sanitizeCollapsed (守卫持久化折叠状态)', () => {
    it('透传合法布尔对象', () => {
      expect(sanitizeCollapsed({ left: true, right: false })).toEqual({ left: true, right: false })
    })

    it('非对象 / null 回退全展开', () => {
      expect(sanitizeCollapsed(null)).toEqual({ left: false, right: false })
      expect(sanitizeCollapsed('x')).toEqual({ left: false, right: false })
    })

    it('字段非布尔或缺失：该字段按 false 处理', () => {
      expect(sanitizeCollapsed({ left: 'yes', right: 1 })).toEqual({ left: false, right: false })
      expect(sanitizeCollapsed({ left: true })).toEqual({ left: true, right: false })
    })
  })
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/utils/importCols.spec.ts`
Expected: FAIL —— `colFlex`/`sanitizeCollapsed`/`RAIL_PX` 未导出。

- [ ] **Step 3: 实现**

在 `frontend/src/utils/importCols.ts` 末尾追加：

```ts
/** 折叠后竖条宽度，像素。 */
export const RAIL_PX = 32

/** 左/右栏的折叠状态（中栏不可折叠）。 */
export interface CollapseState {
  left: boolean
  right: boolean
}

/** 三列的 flex 值与两个分隔条的可见性。 */
export interface ColFlex {
  left: string
  mid: string
  right: string
  showLM: boolean
  showMR: boolean
}

/**
 * 由列宽百分比 + 折叠状态算出三列 flex 与分隔条可见性。
 * 可见列用 `"<pct> 1 0%"`（flex-grow 按比例瓜分剩余空间）；
 * 折叠列用 `"0 0 ${RAIL_PX}px"` 固定细条；折叠那侧分隔条隐藏。
 */
export function colFlex(c: ColWidths, s: CollapseState): ColFlex {
  const rail = `0 0 ${RAIL_PX}px`
  return {
    left: s.left ? rail : `${c.left} 1 0%`,
    mid: `${c.mid} 1 0%`,
    right: s.right ? rail : `${rightOf(c)} 1 0%`,
    showLM: !s.left,
    showMR: !s.right,
  }
}

/** 校验持久化折叠状态；任一字段非布尔即按 false，整体非对象回退全展开。 */
export function sanitizeCollapsed(v: unknown): CollapseState {
  if (typeof v !== 'object' || v === null) return { left: false, right: false }
  const o = v as Record<string, unknown>
  return {
    left: o.left === true,
    right: o.right === true,
  }
}
```

- [ ] **Step 4: 跑测试，确认通过**

Run: `cd frontend && npx vitest run tests/unit/utils/importCols.spec.ts`
Expected: PASS（含原有用例）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/importCols.ts frontend/tests/unit/utils/importCols.spec.ts
git commit -m "$(cat <<'EOF'
feat(import): colFlex + sanitizeCollapsed for collapsible columns

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `ImportSideRail.vue` 折叠竖条组件

**Files:**
- Create: `frontend/src/components/import-v2/ImportSideRail.vue`
- Test: `frontend/tests/unit/ImportSideRail.spec.ts`

- [ ] **Step 1: 写失败测试**

新建 `frontend/tests/unit/ImportSideRail.spec.ts`：

```ts
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ImportSideRail from '@/components/import-v2/ImportSideRail.vue'

describe('ImportSideRail', () => {
  it('渲染传入的 label', () => {
    const w = mount(ImportSideRail, { props: { label: 'Word 原文预览', side: 'left' } })
    expect(w.text()).toContain('Word 原文预览')
  })

  it('左侧 rail 展开箭头为 »', () => {
    const w = mount(ImportSideRail, { props: { label: 'X', side: 'left' } })
    expect(w.get('.rail-expand').text()).toBe('»')
  })

  it('右侧 rail 展开箭头为 «', () => {
    const w = mount(ImportSideRail, { props: { label: 'X', side: 'right' } })
    expect(w.get('.rail-expand').text()).toBe('«')
  })

  it('点击竖条 emit expand', async () => {
    const w = mount(ImportSideRail, { props: { label: 'X', side: 'left' } })
    await w.get('.rail').trigger('click')
    expect(w.emitted('expand')).toHaveLength(1)
  })
})
```

- [ ] **Step 2: 跑测试，确认失败**

Run: `cd frontend && npx vitest run tests/unit/ImportSideRail.spec.ts`
Expected: FAIL —— 组件不存在。

- [ ] **Step 3: 实现**

新建 `frontend/src/components/import-v2/ImportSideRail.vue`：

```vue
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ label: string; side: 'left' | 'right' }>()
const emit = defineEmits<{ (e: 'expand'): void }>()

// 箭头朝向"面板展开的方向"：左条向右开 »，右条向左开 «。
const arrow = computed(() => (props.side === 'left' ? '»' : '«'))
</script>

<template>
  <div class="rail" :title="`展开${label}`" @click="emit('expand')">
    <span class="rail-expand">{{ arrow }}</span>
    <span class="rail-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.rail {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding-top: 10px;
  cursor: pointer;
  background: var(--el-fill-color-light, #f5f7fa);
  border-right: 1px solid var(--el-border-color-lighter, #ebeef5);
  user-select: none;
  color: #606266;
}
.rail:hover { background: var(--el-fill-color, #f0f2f5); color: var(--el-color-primary, #d97757); }
.rail-expand { font-size: 14px; line-height: 1; }
.rail-label {
  writing-mode: vertical-rl;
  letter-spacing: 2px;
  font-size: 12px;
  font-weight: 600;
}
</style>
```

- [ ] **Step 4: 跑测试，确认通过**

Run: `cd frontend && npx vitest run tests/unit/ImportSideRail.spec.ts`
Expected: PASS（4 测试）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/import-v2/ImportSideRail.vue frontend/tests/unit/ImportSideRail.spec.ts
git commit -m "$(cat <<'EOF'
feat(import): ImportSideRail collapsed-column strip

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 在 `ImportDialog.vue` 接线折叠状态 + rail + 分隔条折叠按钮

**Files:**
- Modify: `frontend/src/components/import-v2/ImportDialog.vue`

本任务无独立单测（仓库无 `ImportDialog.spec`，组件依赖大量 api 模块）；由 Gate 的 typecheck/build/全量 test + 手动冒烟覆盖。

- [ ] **Step 1: 引入 rail 组件与折叠工具**

在 `<script setup>` 顶部 import 区：
- 新增组件 import：`import ImportSideRail from './ImportSideRail.vue'`
- 把 `importCols` 的 import 改为追加 `CollapseState`、`colFlex`、`sanitizeCollapsed`：

```ts
import {
  COL_DEFAULTS,
  colFlex,
  resizeLeftMid,
  resizeMidRight,
  sanitizeCols,
  sanitizeCollapsed,
  type ColWidths,
  type CollapseState,
} from '@/utils/importCols'
```

（注意：原 import 里有 `rightOf` 用于 `rightPct` computed —— 见 Step 3 会删掉 `rightPct`，故这里**移除** `rightOf` 导入。）

- [ ] **Step 2: 新增折叠状态**

在 `const cols = useStorage(...)` 与其 `sanitizeCols` 之后追加：

```ts
const collapsed = useStorage<CollapseState>('smartsop.import.collapsed', { left: false, right: false })
// 守卫脏值/旧值
collapsed.value = sanitizeCollapsed(collapsed.value)

const cf = computed(() => colFlex(cols.value, collapsed.value))
```

- [ ] **Step 3: 删除 `rightPct`，因为列宽改由 `cf` 驱动**

删除：

```ts
const rightPct = computed(() => rightOf(cols.value))
```

- [ ] **Step 4: 改模板三列与分隔条**

把 `<div v-else ref="colsRef" class="cols"> ... </div>` 整块替换为：

```html
      <div v-else ref="colsRef" class="cols">
        <div class="col" :style="{ flex: cf.left }">
          <ImportSideRail
            v-if="collapsed.left"
            label="Word 原文预览"
            side="left"
            @expand="collapsed.left = false"
          />
          <WordPreviewPanel v-else :file="ctx.file.value" />
        </div>
        <div
          v-if="cf.showLM"
          class="splitter"
          title="拖拽调整列宽，双击重置"
          @pointerdown="onDragStart($event, 'lm')"
          @dblclick="resetCols"
        >
          <button
            class="collapse-btn"
            title="折叠原文预览"
            @click.stop="collapsed.left = true"
            @pointerdown.stop
          >«</button>
        </div>
        <div class="col" :style="{ flex: cf.mid }"><ImportTreePanel :ctx="ctx" /></div>
        <div
          v-if="cf.showMR"
          class="splitter"
          title="拖拽调整列宽，双击重置"
          @pointerdown="onDragStart($event, 'mr')"
          @dblclick="resetCols"
        >
          <button
            class="collapse-btn"
            title="折叠详情"
            @click.stop="collapsed.right = true"
            @pointerdown.stop
          >»</button>
        </div>
        <div class="col" :style="{ flex: cf.right }">
          <ImportSideRail
            v-if="collapsed.right"
            label="详情"
            side="right"
            @expand="collapsed.right = false"
          />
          <ImportDetailPanel v-else :ctx="ctx" />
        </div>
      </div>
```

- [ ] **Step 5: 加折叠按钮样式 + 让 splitter 能定位按钮**

`.splitter` 已是 `position: relative`。在 `<style scoped>` 末尾追加：

```css
.collapse-btn {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  width: 18px;
  height: 36px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  background: #fff;
  color: #909399;
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}
.splitter:hover .collapse-btn { opacity: 1; }
.collapse-btn:hover { color: var(--el-color-primary, #d97757); border-color: var(--el-color-primary, #d97757); }
```

（按钮 hover 才显形，避免遮挡拖拽热区；点击 `.stop` 不触发拖拽。）

- [ ] **Step 6: 跑 Gate**

Run: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`
Expected: 全绿；测试数 = 既有 + 本次新增（importCols 新 7 + ImportSideRail 4）。lint 0 warning。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/components/import-v2/ImportDialog.vue
git commit -m "$(cat <<'EOF'
feat(import): one-click collapse for 原文/详情 panels

Splitter-hosted collapse chevrons fold the left/right columns into a
32px ImportSideRail; mid grows to fill. Collapse state persists in
localStorage alongside column widths. Side panels untouched.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 收尾

全部任务完成后：
- 跑最终 Gate 确认全绿。
- 用 superpowers:finishing-a-development-branch 收束（合并回 main / PR / 保留 / 丢弃，由用户选）。
- 可选手动冒烟：上传 docx → 点分隔条折叠箭头 → 左/右收成竖条、中栏变宽 → 点竖条展开恢复 → 关闭重开折叠状态保持。

## Self-Review 记录

- **Spec 覆盖：** `colFlex`/`sanitizeCollapsed`(T1)、`ImportSideRail`(T2)、折叠按钮+rail+持久化接线(T3) 全部对应 spec 的"架构/交互/测试/文件清单"。
- **占位符：** 无 TBD；每个代码步骤含完整代码。
- **类型一致：** `CollapseState`/`ColFlex`/`colFlex`/`sanitizeCollapsed`/`RAIL_PX` 在 T1 定义，T3 按同名使用；rail props `{label, side}` 在 T2 定义，T3 按同名传入。
- **既有逻辑不破：** 不改 `resizeLeftMid/resizeMidRight/sanitizeCols/rightOf` 既有导出；拖拽/双击重置只移到可见分隔条；删除 `rightPct` 时同步移除 `rightOf` import（否则 lint 报未用导入）。
