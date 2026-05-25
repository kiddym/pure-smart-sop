# 程序编辑器：树行操作精简 + 空标题定位 + PDF 预览 设计

> 日期：2026-05-25
> 范围：程序编辑页（ProcedureEditorView）四项 UX 改进。移动端执行页**不在本轮范围**，另立项目。

## 背景与问题

程序编辑页的章节树（`ChapterTreePanel` → `TreeRow`）每个章节行 hover 时浮出最多 8 个按钮
（+章 / +容 / +步 / ⇤升级 / ⇥降级 / ↑ / ↓ / ✕），存在三个问题：

1. 按钮占据右半行，hover 时鼠标易落在按钮上而非行上，干扰「点行 = 选中并预览」。
2. ⇤升级 / ⇥降级 与拖拽、`Tab`/`Shift+Tab` 快捷键功能重叠，已无保留必要。
3. 保存校验只提示「有 N 个章节标题为空」，无法定位是哪几个章节；新增多个空章节后用户记不清。

此外评估两个新增预览入口：编辑器内的 PDF 预览（组件已存在，仅详情页在用）与移动端执行页预览
（执行系统目前不存在）。

## 目标

- 章节行动作区从最多 8 个收敛到 4 个可见控件，扩大「点行预览」的可点区域。
- 彻底移除树层级 升级/降级 能力（层级调整今后只靠拖拽）。
- 让空标题章节「边写边可见」，并在保存拦截时自动定位到第一个。
- 编辑器顶栏增加 PDF 预览入口（复用既有弹框）。

## 非目标

- 移动端执行页 / 执行运行时：体量远超本轮，单独 brainstorm + spec。
- 根级工具栏的「+章节 / +内容 / +步骤」改造：它独占一行不拥挤，本轮不动。
- 后端改动：四项均为前端改动，无 API / schema 变更。

---

## 设计

### 1. 话题1 — 章节行操作精简（方案B）

章节行 hover/选中态的动作区 `.tr-actions` 改为四个控件：

```
[＋新增 ▾]   [↑]   [↓]   [⋮]
```

- **＋新增 ▾**：`el-dropdown`，菜单项「子章节 / 内容块 / 步骤」。可用性由
  `store.addButtonStateFor(row.id)`（`AddButtonState`）决定——不可用的项 `disabled`。
  取代原先的 +章 / +容 / +步 三个独立按钮。
- **↑ / ↓**：上移 / 下移，保留（高频，且与拖拽互补），`disabled` 沿用 `canMoveUp/canMoveDown`。
- **⋮ 更多**：`el-dropdown`，当前仅含「删除」（`emit('remove')`）。作为今后低频操作的归处。
- 按节点类型差异化：
  - 章节行：＋新增 ▾ + ↑ + ↓ + ⋮
  - 内容块行：＋新增 ▾（仅当 `addButtonStateFor` 允许，通常无可加项则整组隐藏） + ↑ + ↓ + ⋮
  - 步骤行：↑ + ↓ + ⋮（步骤不能加子节点，无 ＋新增）

行内动作仍只在 hover / 选中该行时出现（`.tr:hover .tr-actions`）。所有动作控件保持
`@click.stop`，点击行本身始终用于选中 + 右侧预览。

**影响文件**：`TreeRow.vue`（模板 + 样式重写动作区；移除 +章/+容/+步 文本按钮，
引入两个 `el-dropdown`）。`ChapterTreePanel.vue` 的 `@add`/`@move`/`@remove` 透传逻辑不变。

### 2. 话题2 — 彻底移除升级/降级

删除树层级 升级/降级（indent/outdent）的全部实现：

- `store/procedureEditor.ts`：删除 `promoteChapter`、`demoteChapter`、`canPromoteChapter`、
  `canDemoteChapter`。
- `useEditorKeyboard.ts`：删除 `Handlers` 的 `onPromote`/`onDemote`，以及 `Tab`/`Shift+Tab`
  分支。
- `ProcedureEditorView.vue`：删除传给 `useEditorKeyboard` 的 `onPromote`/`onDemote` handler。
- `TreeRow.vue`：删除 `canPromote`/`canDemote` props、`promote`/`demote` emits、⇤⇥ 按钮
  （随话题1 重写一并去除）。
- `ChapterTreePanel.vue`：删除 `:can-promote`/`:can-demote` 绑定与 `@promote`/`@demote` 处理。

> ⚠️ **保留** `store.promoteContentToChapter`（内容块 → 章节的类型转换，`ChapterDetailPanel`
> 的「提升为章节」按钮在用）。它与树层级 promote/demote 是不同功能，不在删除范围。

层级调整今后只通过拖拽（`computeDrop`/`moveCrossParent`，已存在）完成。

### 3. 话题3 — 定位空标题章节（方案B + 方案C 增强）

「空标题章节」= `row.kind === 'chapter' && !row.title.trim()`（内容块 / 步骤不计入）。
复用现有「待确认」范式（`review-bar` + `nextReviewId`），结构一致、零学习成本。

**a) 行内标记** —— `TreeRow.vue`
- 空标题章节行加 `tr--missing` 样式：琥珀色左边框（`--warn #e6a23c`）+ 浅底。
- 行内追加「缺标题」标签（复用 `tr-review` 同款琥珀 chip 样式）。
- 判定在 `TreeRow` 内本地计算（已有 `row.kind`、`row.title`）。

**b) 定位条** —— `ChapterTreePanel.vue`
- 工具栏新增一条（镜像 `review-bar`），当 `missingTitleCount > 0` 时显示：
  `⚠ N 个章节缺标题`　`[下一个]`　`[☐ 只看缺标题]`
- `missingTitleCount` = computed，统计上述判定的章节数。
- `gotoNextMissing()`：调用导航工具取下一个缺标题章节 id 并 `selectNode`。
- `missingFilter` ref：开启时 `visibleRows` 经 `keepWithAncestors` 过滤到缺标题节点及其祖先
  （与 `reviewFilter` 同一机制）。

**c) 导航工具** —— `reviewNav.ts`
- 抽出通用 `nextRowId(rows, currentId, predicate)`（文档序、环绕）。
- `nextReviewId` 改为 `nextRowId(rows, id, r => r.mark_status === 'review')`，对外签名不变。
- 缺标题导航：`nextRowId(rows, id, r => r.kind === 'chapter' && !r.title.trim())`。
  （`FlatRow` 已含 `kind`/`title`，无需扩展类型。）

**d) 保存拦截定位** —— `ProcedureEditorView.vue` `doSave`
- `validateForSave` 仍返回错误数组（保持空标题计数项）。
- 当存在空标题章节时：取文档序第一个缺标题章节，`store.selectNode(id)` + 展开其祖先
  （`store.expand`/`toggleExpanded` 链），错误提示文案改为
  「请先补全 N 个章节标题，已定位到 §X」（X 为其 code）。

**e) 方案C 增强（新增即聚焦）** —— `ChapterDetailPanel.vue`
- 标题 `el-input` 加 `ref`；`onMounted` 时若 `chapter.title` 为空则 `focus()`。
- 面板已按 `:key="store.selectedId"` 重建，故每次选中空标题章节（含刚新增的）都会自动聚焦标题框。

### 4. 话题4 — PDF 预览按钮

- `EditorTopBar.vue`：新增「PDF 预览」按钮，`is_current` 时显示（与详情页 `canPdf` 一致），
  `emit('preview-pdf')`。位置：放在主动作区，read-only 时仍可见（PDF 预览对只读也有用）。
- `ProcedureEditorView.vue`：
  - 引入并挂载 `PdfPreviewDialog`（`v-model` + `:procedure-id`）。
  - `onPreviewPdf`：若 `store.isDirty` → `ElMessageBox.confirm`「预览需先保存，是否保存并预览？」
    → 成功 `doSave()` 后打开弹框；否则直接打开。
- 复用既有 `PdfPreviewDialog`（从服务器拉 `fetchProcedureDetail` + `fetchPdfLayout`，故先保存
  可保证预览与当前编辑一致）。

---

## 涉及文件汇总

| 文件 | 改动 |
| --- | --- |
| `components/editor/TreeRow.vue` | 动作区重写为 ＋新增▾/↑/↓/⋮；移除 promote/demote；空标题行标记 |
| `components/editor/ChapterTreePanel.vue` | 缺标题定位条 + 过滤；移除 promote/demote 绑定 |
| `components/editor/EditorTopBar.vue` | 新增 PDF 预览按钮 |
| `components/editor/ChapterDetailPanel.vue` | 空标题章节标题框自动聚焦 |
| `views/procedures/ProcedureEditorView.vue` | PDF 预览挂载 + dirty 保存流程；保存拦截定位；移除 promote/demote handler |
| `composables/useEditorKeyboard.ts` | 移除 Tab/Shift+Tab 与 onPromote/onDemote |
| `utils/reviewNav.ts` | 抽出通用 `nextRowId(rows, currentId, predicate)` |
| `store/procedureEditor.ts` | 删除 promote/demote/canPromote/canDemote；新增缺标题相关 getter |

## 测试

- **单元（`reviewNav`）**：`nextRowId` 的环绕、空集、currentId 不存在；`nextReviewId` 回归。
- **单元（store）**：`missingTitleCount`/缺标题列表的判定（章节 vs 内容块 vs 步骤）；
  确认 `promoteChapter`/`demoteChapter` 已移除而 `promoteContentToChapter` 保留。
- **组件（TreeRow）**：章节行渲染 4 控件；＋新增▾ 菜单项随 `addButtonStateFor` 禁用；
  空标题章节行显示「缺标题」标记；步骤行无 ＋新增。
- **组件（ChapterTreePanel）**：缺标题条计数 / 下一个 / 只看缺标题过滤。
- **集成（ProcedureEditorView）**：保存空标题被拦截并定位到第一个；PDF 预览 dirty 时先提示保存；
  无 Tab/Shift+Tab 缩进行为。

## 风险与权衡

- **移除升级/降级**：失去键盘缩进；层级调整仅剩拖拽。用户已确认接受。
- **PDF 预览反映已保存版本**：通过 dirty 时强制「保存并预览」消除不一致。
- **缺标题持续提醒可能对刚新增的章节略显啰嗦**：可接受——标记轻量（左边框 + chip），
  且方案C 自动聚焦会引导用户立刻补全。
