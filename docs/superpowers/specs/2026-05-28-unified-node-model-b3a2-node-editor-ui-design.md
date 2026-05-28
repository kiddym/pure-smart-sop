# 统一节点模型 B3a-2 — 节点编辑器 UI 设计

> 本文细化 `2026-05-28-unified-node-model-b3-frontend-design.md`（B3a §「新建节点编辑器 behind flag」）的 **UI 层**。数据层（`api/nodes.ts` + `Node` 类型 + `utils/nodeTree.ts` + `nodeEditor` store）已在 **B3a-1** 实现并合并 main（merge `030588c`）。本文只补 B3a-2 的视图/组件设计、为 UI 必需的小幅 store 增补、复用清单、拆分与测试策略。母 spec：`2026-05-28-unified-node-model-design.md` §6（前端）/§3（转换语义）。

## 背景与关系

- Plan B 渐进双写：B1（导入双写）✅、B2a（全写入路径同步 node）✅、B2b（PDF 读 node）✅、**B3a-1（前端数据层）✅** 均已并入 main。
- **B3a-2 = 节点编辑器 UI**：在 `?editor=node` flag 下新建一个**完整、隔离**的节点编辑器，消费 B3a-1 的 `nodeEditor` store；旧编辑器零改动、仍是默认。合并后 app 行为不变（新编辑器仅经 flag 可达，供开发/测试）。
- 之后是 **B3b**（切换路由去 flag + 删旧面板/layerMark/markMode/save_procedure + 改造 review/batchMark），再 **B4 contract**（停双写、删旧表与死端点、重建 dev.db）。

## 锁定决策（本次 brainstorm）

### D1 — 挂载：独立 `NodeEditorView` 经 `?editor=node`
`ProcedureEditorView.vue` 在 setup/onMounted 读 `route.query.editor`：等于 `'node'` 时渲染新的、自包含的 `NodeEditorView.vue`；否则渲染现有编辑器（**不动一行**）。两个 store 不纠缠：node 模式下只 `nodeEditor.load(id)`，**不** load `procedureEditor`。B3b 只需把默认翻到 `NodeEditorView` 并删旧 view。

- 理由：B3a 要求「新建完整编辑器、旧的原封不动、behind flag」。独立 view 给最干净的隔离 + 最简单的 B3b 切换；代价是复制一份轻量 top-bar/布局壳（可接受）。
- 注（[[editor-route-reuse-no-reload]]）：flag 经「直接加载带参 URL」进入，`onMounted` 触发一次即可，不涉及 editor→editor 复用不重载的坑。

### D2 — Chrome：最小（back + undo + autosave 状态）
node 编辑器**即时·乐观·颗粒度写**（每次编辑直调 node API），故**无 Save 按钮、无 dirty 跟踪**。top bar 仅：`[< 返回]　程序标题/面包屑　[↶ 撤销]　[✓ 已保存 / 保存中…]`。

- **发布 / 版本 / PDF 预览 / 升级·复制·废弃**等程序生命周期动作 **不在 B3a-2**——继续用默认（旧）编辑器，留到 B3b 切换时统一接。node 模式因此**无需 load `procedureEditor`**。
- autosave 状态读新增的 `nodeEditor.saving`（见 §「store 增补」）；写错误已由 `http` 拦截器 toast。

### D3 — 拖拽：子树感知、仅 before/after
统一模型里父子是**派生**的（某节点的父 = 其前面最近的、`heading_level` 更小的节点）。因此拖拽换位即自动改派生父：
- 拖**标题**节点 → 连同其全部后代作为一个**连续块**整体移动；拖**叶子** → 只动自己。
- 落点只有目标行的 **before/after**，**无「drop inside」**。要嵌套：拖到某标题之后，或用行内 chip 改 `heading_level`。
- 一次拖拽 = 计算新的全量 `ordered_ids` → 一次 `store.reorder(orderedIds)`（后端按新序 + 现有 heading_level 重派生父，store re-GET 全量）。
- 理由：契合派生模型、避免「拖拽也改 level」的双重真值源；复用既有 `reorder` action。

## B3a-2 组件设计（每单元一清晰职责）

| 文件 | 职责 | 动作 |
|---|---|---|
| `src/views/procedures/NodeEditorView.vue` | 隔离壳：onMounted `nodeEditor.load(id)` + 取程序 meta（标题）；布局（top bar + 左树/右详情两栏）；撤销按钮（`undo`/`canUndo`）；autosave 指示（`saving`）；返回。 | 创建 |
| `src/components/editor/NodeTreePanel.vue` | 渲染 `store.rows`：搜索、review 过滤/计数/下一个、根级新建按钮、γ 多选浮动条、虚拟列表。 | 创建 |
| `src/components/editor/NodeTreeRow.vue` | 单行：depth 缩进、α level chip（正文/L1..3→`setLevel`、kind 切换→`setKind`）、多选 checkbox、review 徽章、删除、原生 HTML5 拖拽句柄。 | 创建 |
| `src/components/editor/NodeDetailPanel.vue` | `store.selectedNode` 详情：body `RichTextEditor`→`updateBody`（防抖）；level/kind/skip chip；`kind==='step'` 时 `StepFormFields`+`FormFieldPreview`+`attachment_marks`→`updateForm`；review 确认→`confirmReview`。 | 创建 |
| `src/utils/nodeTreeDnd.ts` | `computeReorder(rows, dragId, targetId, position)→orderedIds`（子树感知、before/after）。 | 创建 |
| `src/store/nodeEditor.ts` | 增 `batchSetKind(ids, kind)` + `saving` 标志（见下）。 | 修改（追加） |
| `src/views/procedures/ProcedureEditorView.vue` | 仅加 flag gate `v-if`（`route.query.editor==='node'` → `<NodeEditorView/>`，否则现状）。 | 修改（最小） |
| `src/router/index.ts` | 若需，确保 `?editor=node` 在 `/procedures/:id/edit` 下可达（query 不改路由匹配，通常无需改；以实现为准）。 | 视情况 |

### store 增补（B3a-2 内，小幅）
- **`batchSetKind(ids, kind)`**：γ 浮动条「设为 step/正文(kind)」需批量改 kind；B3a-1 只有 `batchSetLevel`。与之对称，经 `batchUpdateNodes(procId, {[id]:{kind}})`，记逆操作入撤销栈。
- **`saving: boolean`**：在每个 mutating action 进入时置 true、`finally` 置 false，供 top bar autosave 指示读取。`load` 用既有 `loading`。

### 复用（不重写）
- `RichTextEditor.vue`（`@wangeditor`，`v-model` + `variant='full'` + `:procedureId`）：body 编辑。
- `StepFormFields` / `FormFieldPreview` / `FORM_TYPE_META`（`@/utils/editor`）：step 表单与预览。
- `utils/batchMark.ts`（`buildSelection`/`buildCascadeSelection`，`MAX_BATCH_MARK=100`）：多选 + shift 区间 + 上限。经**薄适配器**把 `TreeRow.node → {id, kind, parent_id, depth}` 喂入；`kind==='chapter'` skip 分支对 node kinds（`'node'|'step'`）天然不触发（正式删除留 B3b）。
- `utils/reviewNav.ts`（`nextReviewId`）：review 导航。
- 虚拟列表 `@vueuse/core::useVirtualList`（阈值 ~50），镜像旧 `ChapterTreePanel`。

### 编辑语义（§3 镜像，前端只发 API、后端派生）
- chip 选 level/正文/step → 单节点 `setLevel`/`setKind`（降级子上提、升级接管后续正文均由后端派生、store 拿新全量 list 重渲染）。
- γ 浮动条「设为 正文/Lx/step」→ `batchSetLevel`/`batchSetKind`（`:batch`，被改的 `review` 节点由后端清回 `unmarked`）。
- review 确认 → `confirmReview`（空 `:batch` change，后端清 review）。
- body / step 表单 → `updateBody`/`updateForm`（`PATCH /nodes/{id}`，If-Match revision）。
- 撤销 → `undo`（B3a-1 已实现线性逆操作；redo 留后续）。

## 拆分与顺序

**一个 plan、一条分支** `feat/unified-node-model-b3a2`，task-by-task 带评审检查点（不再拆子分支）。建议 task 序：

1. store 增补（`batchSetKind` + `saving`）+ vitest。
2. `utils/nodeTreeDnd.ts`（`computeReorder` 子树感知）+ vitest。
3. `NodeDetailPanel.vue` + vitest（body/level/kind/skip/step 表单/attachment/review 确认）。
4. `NodeTreeRow.vue` + `NodeTreePanel.vue` + vitest（行渲染/缩进/chip/多选+浮动条/review 徽章·过滤/搜索/新建·删除/拖拽）。
5. `NodeEditorView.vue` + `ProcedureEditorView` flag gate（+ 路由按需）+ vitest。
6. 全量前端回归（`vitest`）+ 类型（`vue-tsc --noEmit`）+ lint（`eslint --max-warnings 0`）+ 经 `running-smartsop-dev` 手动驱动真实 `?editor=node` URL（chrome-devtools）。

每合并前：前端全测绿、类型/lint 干净、app 默认行为不变（旧编辑器零回归）；后端不受影响。

## 测试策略（vitest）

- **store 增补**：`batchSetKind` 的 `:batch` payload + 全量替换 + 撤销；`saving` 在 action 期间翻转。
- **nodeTreeDnd**：`computeReorder` 各情形——叶子前/后移、标题带子树整体移、移到列表首/尾、no-op。
- **NodeDetailPanel**：body 编辑触发 `updateBody`、level/kind/skip chip、step 表单与 attachment 触发 `updateForm`、review 确认触发 `confirmReview`。
- **NodeTreeRow / NodeTreePanel**：给定扁平 list + heading_level → 正确缩进/父子；chip；多选 + 浮动条调 `batchSetLevel`/`batchSetKind`；review 徽章/过滤/计数；搜索；新建/删除；拖拽经 `computeReorder` → `reorder`。el-dropdown 菜单在 jsdom 不渲染（[[el-dropdown-jsdom-test]]）——测 `@command` 走组件 `$emit`，不手搓菜单。
- **flag gate**：`ProcedureEditorView` 在 `?editor=node` 渲染 `NodeEditorView`、否则渲染旧编辑器。

## 范围边界与延后

- **B3a-2 纯前端**：node API（Plan A）+ 数据层（B3a-1）已在；本期零后端改动。
- **延后到 B3b**：切换默认路由（去 flag）；删 `ChapterTreePanel`/旧详情面板/`layerMark`/标记模式 UI/`save_procedure`/`applyLayerRoles`；把 `review`/`batchMark` 正式迁入新树（删 chapter-skip）。
- **延后到 B3 之后纯增量 pass**：β 键盘（`Cmd+1..4`/`Tab`）+ δ markdown（`## `/`Backspace`）。
- **本期不做**：发布/版本/PDF 预览/升级·复制·废弃 chrome（用旧编辑器）；redo（store 字段已预留）；跨标签 412 冲突精修；heading 多段 body「引言」编辑 nicety（母 spec §2.3 末）。

## 待规划期确认的小项（非阻塞）
- 取程序 meta（标题/面包屑）的现有只读 API（写 plan 时核对 `src/api/procedures.*` 实际函数；display-only）。
- `?editor=node` 是否需动 `router/index.ts`（query 通常不改匹配，预计无需；以实现为准）。
- `saving` 指示是否对**极快**的本地往返产生闪烁——必要时加最小显示时长（实现细节，plan 内决定）。
