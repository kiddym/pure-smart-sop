# 标记模式：章节级联勾选 + step↔content 批量切换

**日期**：2026-05-26
**作用范围**：前端编辑器 — 章节树标记模式（mark mode）
**后端变更**：无

## 1. 背景与目标

当前编辑器的「标记模式」只允许 chapter 行被勾选；shift-range 已经在 `buildSelection` 中支持 content 行（但 TreeRow 不渲染 content 的 checkbox，已是隐性不一致），并显式跳过 step 行。批量操作面对一颗几十节的章节树时，仍需逐行点击或逐段 shift 选。

本设计在 mark mode 中加入：

1. **章节级联勾选**：点击章节 checkbox 自动勾选/取消其下所有后代（章节 + content + step）。
2. **step / content 也可勾选并被批量切换 kind**：复用现有 `setStepKind` 立即翻转。

不在范围内：step → chapter（受 §Q25 sibling mutex 影响，单行操作更稳）；后端 schema 变更；为 step 增加 `mark_status` 字段。

## 2. 行为规范

### 2.1 Checkbox 渲染

进入 mark mode 时，**所有 kind 的行都渲染 checkbox**（chapter / content / step）。今日 `TreeRow.vue:82` 的 `v-if="markMode && row.kind === 'chapter'"` 调整为 `v-if="markMode"`。

### 2.2 章节 checkbox 级联点击规则

| 当前章节 checkbox 状态 | 点击效果                                    |
| ---------------------- | ------------------------------------------- |
| unchecked              | 勾选章节 + 级联勾选所有后代                 |
| indeterminate（半选）  | 勾选章节 + 级联勾选**剩余**后代             |
| checked                | 取消勾选章节 + 级联取消所有后代             |

「半选」由 `el-checkbox` 的 `indeterminate` prop 控制。当章节的部分（≥1 且 < 全部）后代在选择集合中时，章节 checkbox 自身**不**进集合，只显示半选。

### 2.3 叶子行 checkbox

step / content 行的 checkbox 只切换自身。父章节的 indeterminate / checked 状态由 selection 派生，自动重算。

### 2.4 Shift-range 行为

保持现有同父约束；但**取消** `if (r.kind === 'step') continue`，所以 shift-range 现在可包含 step 行。跨父部分仍忽略并保留原有 toast。

### 2.5 级联范围

**全子树，忽略 expand/filter 状态**。即使章节当前折叠或被搜索/review/missing 过滤器隐藏，其后代仍参与级联。这是最简单的心智模型，与操作系统文件管理器一致。

### 2.6 100 项上限

级联结果超过 `MAX_BATCH_MARK`（100）时，按 DFS 顺序截断到前 100 项，沿用现有告警 `单次最多标记 N 项，已保留前 N 项`；锚点若被截掉则置 null。

### 2.7 退出模式

不变：`watch(() => store.markMode)` 在 `ChapterTreePanel.vue:223` 关闭时清空 `markSel` 与 `lastChecked`。

## 3. Apply 语义

### 3.1 「标记为步骤」/「标记为内容」按钮分发

| 选中行 kind | 目标 = 'step'                       | 目标 = 'content'                      |
| ----------- | ----------------------------------- | ------------------------------------- |
| chapter     | `setMark(id, 'step')`（现状）       | `setMark(id, 'content')`（现状）      |
| step        | 跳过（已是 step）                   | `setStepKind(id, 'content')`          |
| content     | `setStepKind(id, 'step')`           | 跳过（已是 content）                  |

调用顺序：先 `ensureSaved()` 拿到 temp→real id map，再分 kind 路由。完成后 toast：

```
已标记 N 项（K 项就地转换）
```

K = 实际触发 `setStepKind` 的次数（即 step/content 跨 kind 切换）。K=0 时省略括号。

### 3.2 立即翻转语义（B1）

step ↔ content 通过 `setStepKind` 立即翻转，复用现有路径：

- `setStepKind` 已经 `pushUndo()`（`store/procedureEditor.ts:580`），所以 Ctrl-Z 可撤销。
- step → content 会清空 `input_schema` / `attachment_marks` / `title`（`store/procedureEditor.ts:583-585`）——这是**现有**行为，与 more 菜单「转为内容块」一致。批量入口不引入新破坏性。
- chapter mark 仍然是「预览」语义（图标颜色变，应用后才落库）；step kind 翻转是「立即」语义。toast 中的 `K 项就地转换` 明示此差异。

### 3.3 「应用标记」与「清除标记」

- **应用标记**：流程不变。`ensureSaved()`（会顺带 flush dirty 的 step kind 改动）→ `applyMarks` 后端调用（只处理 chapter mark）。
- **清除标记**：作用域不变——只清 chapter 的 `mark_status`。step/content 的 kind 改动是真实编辑，不在「清除标记」范围内；要回退请用 Ctrl-Z。

## 4. 文件改动

### 4.1 `frontend/src/utils/batchMark.ts`

1. 删除 `buildSelection` 内的 `if (r.kind === 'step') continue`。
2. 新增 `buildCascadeSelection`：

```ts
export interface CascadeParams {
  current: ReadonlySet<string>
  anchor: string | null
  rootId: string                // 被点击的章节 id
  descendantIds: string[]       // rootId 的全部后代（DFS 顺序）
  action: 'select' | 'deselect' // 由调用方根据当前状态判定
}

export function buildCascadeSelection(p: CascadeParams): SelectionUpdate
```

`action='select'`：把 `rootId` 与每个 `descendantIds[i]` 加入集合；`action='deselect'`：移除之。100 项上限与现有告警逻辑复用。锚点移到 `rootId`，若被截断则置 null。

### 4.2 `frontend/src/components/editor/TreeRow.vue`

1. `v-if="markMode && row.kind === 'chapter'"` → `v-if="markMode"`。
2. 新 prop `indeterminate: boolean`（默认 false），传给 `el-checkbox` 的 `indeterminate`。叶子行恒为 false。
3. drag guard `:draggable="editable && !markMode"` 不变。

### 4.3 `frontend/src/components/editor/ChapterTreePanel.vue`

1. **后代映射**：`computed<Map<string, string[]>>`，由 `store.chapters`（parent_id）与 `store.steps`（chapter_id）派生，每个 chapter id → 全部后代 id（DFS 顺序）。响应于 chapters/steps 的结构变化。
2. **半选集合**：`computed<Set<string>>`，从 `markSel` 与后代映射派生：descendant 命中数 ∈ (0, total) 的 chapter id 入集合。
3. **`onCheck(row, shift)` 分发**：
   - chapter + 非 shift：根据当前状态判 action（unchecked / indeterminate → `select`；checked → `deselect`），调 `buildCascadeSelection`。
   - chapter + shift：走现有 `buildSelection`（shift 仍是 range 语义，不级联）。
   - 非 chapter（step / content），任意修饰键：走现有 `buildSelection`。
4. **`applyBatch(status)` 重写**：

```ts
async function applyBatch(status: 'step' | 'content'): Promise<void> {
  const ids = [...markSel.value]
  const map = await store.ensureSaved()
  let inplace = 0
  for (const id of ids) {
    const real = map[id] ?? id
    const ch = store.chapterMap.get(real)
    if (ch) {
      await store.setMark(real, status)
      continue
    }
    const st = store.stepMap.get(real)
    if (st && st.kind !== status) {
      store.setStepKind(real, status)
      inplace++
    }
  }
  ElMessage.success(`已标记 ${ids.length} 项${inplace ? `（${inplace} 项就地转换）` : ''}`)
  markSel.value = new Set()
}
```

5. 在 `<TreeRow>` v-for 中传 `:indeterminate="indeterminateSet.has(row.id)"`。

### 4.4 `frontend/src/store/procedureEditor.ts`

无新方法。后代映射留在 panel；若日后出现第二消费者再上提到 store。

### 4.5 `frontend/src/types/node.ts`

`FlatRow.mark_status` 行注释（line 185）今为 `// step 恒 'unmarked'（不参与标记模式）`，删除括号——step 现在参与标记模式。`mark_status` 字段在 step 上仍恒为 'unmarked'（后端无此字段），所以前半句保留。

## 5. 测试

### 5.1 单元测试 — `frontend/src/utils/__tests__/batchMark.spec.ts`

1. shift-range 现在包含 step：同父 shift 跨过 step 行时该行被选中。
2. `buildCascadeSelection` select：空集合 + 章节级联 → 结果含 rootId + 每个 descendantId；anchor = rootId。
3. `buildCascadeSelection` deselect：含全部 → 移除全部；anchor = rootId。
4. 级联超 100：descendantIds.length = 150 → 结果截断到 100，告警发出，锚点若不在结果集则 null。
5. 半选状态下 select：当前有 3 个后代 → 调用方传 action='select' → 全 10 后代 + rootId 入选。

### 5.2 组件测试 — `frontend/src/components/editor/__tests__/ChapterTreePanel.spec.ts`

（先确认是否已有该文件；若无则建。）

6. indeterminate 渲染：章节 C + 3 子，勾选 1 个 → C 的 checkbox `indeterminate=true`。
7. 半选 chapter 被点：续 #6 → 点 C → 4 id 全入选，indeterminate=false，checked=true。
8. `applyBatch('content')` 按 kind 分发：选 1 chapter + 1 step + 1 content，stub `store.setMark` 与 `store.setStepKind`：
   - `setMark` 调用 1 次，参数 `(chapterId, 'content')`
   - `setStepKind` 调用 1 次，参数 `(stepId, 'content')`
   - content 行**不**触发 `setStepKind`
   - toast 文案 `已标记 3 项（1 项就地转换）`
9. 退出模式清空 selection：已有覆盖，确认无回归。

### 5.3 不测的

- 「级联忽略 filter」规则：实现上就是从 store 传 descendants 而非 `visibleRows`，单测会变成测试构造。组件测试 #8 隐式覆盖。
- 后端：无变更。
- E2E：超出本变更范围；现有 mark mode happy-path E2E（如有）应保持通过。

## 6. 风险与权衡

- **chapter mark 与 step kind 翻转的时机不一致**（预览 vs. 立即）。已通过 toast 中的「K 项就地转换」明示；与现有 more 菜单「转为内容块」一致；Ctrl-Z 可救。
- **step → content 的字段丢失**（`input_schema` / `attachment_marks` / `title`）。这是现有行为；批量入口让一次操作丢失范围更大，但与单行行为一致，不视为新风险。
- **隐藏后代被静默选中**：filter 当前为 `keepWithAncestors`，被过滤的后代仍在 selection 中。已在 §2.5 接受此 trade-off，未来可加 toast「X 项不在当前视图但已包含」。
- **章节 mark_status 写后端是即时的**（`setMark` 在面板点击时就 PUT；今日如此）。本变更不动这条路径——级联章节 selection 不会立刻 PUT mark_status，只在「标记为...」按钮按下时才走。
