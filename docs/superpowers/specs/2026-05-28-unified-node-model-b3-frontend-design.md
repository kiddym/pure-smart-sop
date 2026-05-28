# 统一节点模型 B3 — 前端节点编辑器设计

> 本文是 `2026-05-28-unified-node-model-design.md` §6（前端改动）的**实施级细化**，记录 B3 brainstorm 的架构决策与子计划拆分。UX 细节（4 条输入路径形态、组件合并、删除/保留清单）以 §6 为准，本文不重复，只补 §6 未定的**写入模型、MVP 取舍、拆分与切换策略**。

## 背景与关系

- Plan B 渐进双写：B1（导入双写 node）✅、B2a（所有写入路径同步 node）✅、B2b（PDF 读 node）✅ 均已并入 main。
- **B3 = 前端切到统一节点编辑器**：编辑器读 `GET /procedures/{id}/nodes`、写 §4 的颗粒度 node API；删层级标定模式 + 标记模式 UI；保留 `review` 待确认链路 + `batchMark` 多选逻辑（§6）。
- B3 之后是 **B4 contract**（停双写、删旧表 + `numbering_service`/`node_sync`/`chapter_service` + 死端点 + 重建 dev.db）。

## 锁定决策（brainstorm 结论）

### D1 — 写入模型：颗粒度·即时·乐观（spec-faithful）
编辑器放弃「本地攒改 + 一次 `PUT /procedures/{id}`(save_procedure)」的批量模型，改为**每次编辑即时调 node API**：
- 改层级/kind → `PATCH /nodes/{id}`（§4「转换唯一入口」）；多选批量 → `PATCH .../nodes:batch`；改 body → `PATCH /nodes/{id}`；增/删/移 → `POST` / `DELETE` / `reorder`。
- **乐观更新**：本地先改、带该 node 的 `revision` 发请求；409 冲突 → 回滚该节点并提示（按 §4 乐观锁）。
- **撤销**：客户端维护「编辑操作历史」，`Cmd+Z` 发出该操作的**逆 node-API 调用**（乐观），取代旧的整树快照撤销（§6.1）。

理由：§4 把 node API 设计成颗粒度 + per-node revision，`PATCH` 是转换唯一入口；§6.1 要求即时 optimistic + `Cmd+Z`。批量 save_procedure 与之冲突（无 batch-upsert-temp-id 端点、revision 对不上）。这也是 B4 终态（编辑器直写 node、删 save_procedure）。

### D2 — MVP 输入路径：α inline chip + γ 多选浮动条；β/δ 延后
首切只做 **α（行首 level chip → 单节点 PATCH）** 与 **γ（多选浮动条 → :batch）**——覆盖新手单行 + 导入后批量清理，且行使全部转换语义。**β（键盘 `Cmd+1..4`/`Tab`）与 δ（markdown `## `/`Backspace`）延后到 B3 之后的纯增量 pass**（无新后端，可平滑叠加）。create/delete/拖拽 reorder、body 编辑、step 表单、`review` 链路**不在延后之列**（编辑器基本功能，B3a 必含）。

### D3 — 拆分：B3a 旗下新建 → B3b 切换并删旧（各自合 main 绿、app 全程可用）
编辑器是中心 UI，读写都要翻到 node，无法半迁移还可用。故**并行新建 + 一次切换**：
- **B3a**：在 flag/平行路由下**新建完整节点编辑器**，旧编辑器原封不动仍是默认。合并后 app 不变（新代码经 flag 可达，供开发/测试）。
- **B3b**：把编辑器路由切到新面板（去 flag），**删旧**（见下），保留改造 `review`/`batchMark`。

---

## B3a 设计 — 新建节点编辑器（behind flag）

### 文件与职责（每个单元一个清晰职责）

| 文件 | 职责 |
|---|---|
| `src/api/nodes.ts` | node API 客户端：`listNodes(procId)`=GET、`patchNode(id, changes, revision)`=PATCH、`createNode(procId, payload)`=POST、`deleteNode(id)`=DELETE、`reorderNodes(procId, orderedIds)`=POST reorder、`batchUpdateNodes(procId, updates)`=PATCH :batch。薄封装 + 类型。 |
| `src/types/node.ts`（增） | 统一 `Node` 类型（对齐后端 `NodeOut`）：`id, procedure_id, sort_order, heading_level:int\|null, kind:'node'\|'step', body, code, skip_numbering, input_schema, attachment_marks, mark_status, revision, parent_id, depth`。 |
| `src/store/nodeEditor.ts`（新 store/composable） | 持 `nodes`(扁平,带派生 parent_id/depth/code)、`selectedId`、`expanded`、多选 `selection`、`reviewFilter`；派生 `flatRows`(按 expanded 折叠)。编辑 action 即时调 api/nodes + 乐观更新 + per-node revision + 409 回滚；维护 undo 操作历史。 |
| `src/components/editor/NodeTreePanel.vue` | 渲染派生树：行首 level chip（α）、多选 checkbox（γ）、`review` 徽章 + 过滤、搜索、拖拽 reorder、create/delete 动作。 |
| `src/components/editor/NodeDetailPanel.vue` | 选中节点详情：body 富文本（→PATCH body）、heading_level/kind chip、`kind='step'` 时 input_schema 表单 + attachment_marks（吸收旧 StepDetailPanel）、review 确认。 |
| flag/路由 | 经 `?editor=node` flag 或平行路由挂载新编辑器；旧编辑器仍默认。 |

### 复用（不重写）
- `src/utils/batchMark.ts`：多选 shift 区间 + 100 上限 + 跨父告警**逻辑保留**；改造点留到 B3b（删 `kind==='chapter'` skip）——B3a 先按现状复用于 node 多选（node 无纯容器章节，skip 分支对 node 自然不触发）。
- `src/utils/reviewNav.ts`：`nextReviewId` 复用。

### 编辑语义（§3 镜像，前端只发 API、后端派生）
- chip 选层级/正文/step → `PATCH {heading_level}` 或 `{kind}`（降级子上提、升级接管后续正文都由后端派生树自动完成，前端拿新 list 重渲染，§3.2/§3.5）。
- 多选浮动条「设为 正文/Lx/step」→ `:batch`；被改的 `review` 节点 `mark_status` 由后端清回 `unmarked`（§6.4）。
- review 确认 = `PATCH {mark_status:'unmarked'}` 或编辑其 level/kind（后端清）。

### 乐观/撤销细节
- 每个 node 在 store 里带 `revision`；`PATCH`/`:batch` 后用返回值更新 revision。409 → 重取该 node（或整列表）+ 提示，丢弃本地该步。
- undo 历史记录每个已提交操作的逆操作（如 level a→b 的逆是 b→a 的 PATCH；create 的逆是 delete；等）。`Cmd+Z` 乐观发逆操作。reorder/移动子树的逆 = 反向 reorder。

### 测试（vitest）
- `api/nodes` 客户端：各方法 URL/payload/revision 头（mock http）。
- `nodeEditor` store：load→flatRows 派生、chip PATCH 乐观 + 回滚、:batch、create/delete/reorder、review 确认、undo 逆操作。
- `NodeTreePanel`：给定扁平 list + heading_level → 正确缩进/父子、chip、多选、review 徽章/过滤（el-dropdown 菜单在 jsdom 不渲染，按 memory `el-dropdown-jsdom-test` 测 `@command` 走组件 `$emit`，不手搓菜单）。
- `NodeDetailPanel`：body 编辑触发 PATCH、step 表单、review 确认。

---

## B3b 设计 — 切换 + 删旧

### 切换
- `ProcedureEditorView` 默认渲染 `NodeTreePanel` + `NodeDetailPanel`（去 flag/平行路由）；保留 `EditorTopBar`、版本/发布/PDF 对话框等无关组件。

### 删除（§6.3 / §9）
- `ChapterTreePanel.vue`、`layerMark.ts`(+`validateLayerQ25`/`computeLayerUpdates`/`computeLayerIndents`/`effectiveRole`/`LayerRow`)、层级标定模式 UI、`extracted_titles`/`collapsed_chapters` toast。
- 标记模式 UI：`store.markMode` 进退、tree 里 mark-mode 分支、`mark_status` 的 step/content 图标色映射（**`review` 徽章保留**）。
- 旧 `ChapterDetailPanel`/`ContentDetailPanel`/`StepDetailPanel`（并入 NodeDetailPanel）、`ContentDetailPanel` 的 title placeholder。
- 旧 `procedureEditor.ts` 里**切换后死掉的批量路径**：`applyLayerRoles` action、`save_procedure`/`buildPayload`/dirty 跟踪/temp-id（新编辑器走颗粒度写，不再用）。若整个旧 store 死透则整删；若 `EditorTopBar`/其他仍依赖部分 getter，则只删死代码。
- 废测试：`layerMark.spec.ts`、`procedureEditor.applyLayerRoles.spec.ts`、标记模式相关 spec。

### 保留并改造
- `review` 待确认全链路迁到 `NodeTreePanel`（徽章 + reviewCount + reviewFilter + 确认动作 + 发布前阻断）。
- `batchMark.ts`：删 `if (r.kind === 'chapter') continue`（§6.4）。

---

## 范围边界与 B4 延后

- **B3 纯前端**：node API（Plan A）已存在，B3 不动后端。
- **切换后变死、但删除延后到 B4** 的后端：`apply-layer-roles`/`apply-marks`/`convert_to_*` 端点 + `LayerApplyResult`/`ApplyMarksResult` schema、`save_procedure` + `GET /procedures/{id}` 详情的 chapters/steps 装配（PDF 已不读，B2b；编辑器切换后也不读）。B3 只「停止调用」，删除随 B4 旧表一起。
- **β 键盘 + δ markdown 输入路径**：B3 之后的纯增量 pass。
- **heading 多段 body 的「引言」编辑 nicety**（§2.3 末）：本期不做。

## 子计划与顺序

1. **B3a**（plan 待写）：新建 node 编辑器 behind flag + vitest。合 main 绿、app 不变。
2. **B3b**（plan 待写）：切换路由 + 删旧 + 改造 review/batchMark。合 main 绿、app 跑新编辑器。

每子计划合并前全测绿（后端 `backend/.venv/bin/python -m pytest` 不受影响 + 前端 `vitest`）；手动 dev 验证用 `running-smartsop-dev`（前端 5173 / 后端 8000）。
