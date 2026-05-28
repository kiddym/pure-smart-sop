# 统一节点模型 B3b — 切换默认编辑器 + 删旧 设计

> 本文细化母 spec `2026-05-28-unified-node-model-b3-frontend-design.md` §「B3b 设计 — 切换 + 删旧」。B3a-1（数据层）+ B3a-2（节点编辑器 UI，behind `?editor=node`）已实现并合并 main（B3a-2 merge `e5a0869`）。本文落实 **B3b 的切换策略、shell 复用与 store 收窄、只读模式、metadata 即时存、删除清单、拆分（B3b-1 切换 / B3b-2 删旧）**。母 spec：`2026-05-28-unified-node-model-design.md` §6（前端）/§3（转换语义）。

## 背景与关系

- Plan B 渐进：B1 导入双写 ✅、B2a 全写入同步 ✅、B2b PDF 读 node ✅、**B3a-1 前端数据层 ✅**、**B3a-2 节点编辑器 UI（behind flag）✅** 均已并入 main。
- **B3b = 把编辑器切到统一节点编辑器并删旧**：去 `?editor=node` flag、新面板成默认；删旧章节/内容/步骤树 + 详情面板 + 层级标定 + 标记模式 + 批量 `save_procedure`；保留并迁移 `review`/`batchMark`。合并后 app 默认即新编辑器、旧结构编辑代码删除。
- 之后是 **B4 contract**：停双写、删旧表（`ProcedureChapter`/`ProcedureStep`）+ `numbering_service`/`node_sync`/`chapter_service` + 后端死端点（`apply-marks`/`apply-layer-roles`/`convert_to_*`/`save_procedure` 的 chapters/steps 装配）+ 重建 dev.db。

## 锁定决策（本次 brainstorm）

### D1 — 切换策略：复用 shell、只换核心（Strategy A）
`ProcedureEditorView` 仍是 `/procedures/:id/edit` 与 `/procedures/:id/view` 的路由目标。**去掉 `?editor=node` gate**，编辑器主体**恒**渲染统一面板。B3a-2 的独立壳 `views/procedures/NodeEditorView.vue` **退役**（其 `nodeEditor.load(id)` + 取 meta + 撤销 + autosave-`$onAction` 逻辑并入 `ProcedureEditorView`）；其真正价值（`NodeTreePanel`/`NodeTreeRow`/`NodeDetailPanel`/`nodeEditor` store/`utils/nodeTreeDnd`）全部复用。

- **保留（shell，原样复用）**：`EditorTopBar`（生命周期 chrome）、`EditorPreviewPane`（Word 原文预览）、`ProcedureDetailsPanel`（程序元数据/自定义字段）、`AttachmentPanel`、版本历史、`PublishChecklistDialog`/`VersionActionDialog`/`PdfPreviewDialog`。
- **替换**：`ChapterTreePanel` → `NodeTreePanel`；`ChapterDetailPanel`/`ContentDetailPanel`/`StepDetailPanel`（按 selected kind 三选一）→ `NodeDetailPanel`（统一）。两者绑 `nodeEditor` store。
- 理由：生命周期/元数据/附件/版本/Word 预览/只读模式都是与「章节→节点」迁移正交的 shell 功能，已可用。复用 shell = 最少新增、最低风险，且与母 spec 一致（「保留 EditorTopBar、版本/发布/PDF 对话框等无关组件」）。代价：退役 B3a-2 的薄壳 `NodeEditorView`（其逻辑并入，非丢弃）。

### D2 — 双 store，职责清分（slim `procedureEditor`）
- **`nodeEditor`**（B3a-1，不改）：持结构（树 + 详情，即时·乐观·颗粒度写）。`ProcedureEditorView` onMounted 调 `nodeEditor.load(id)`。
- **`procedureEditor`（收窄为「元数据 store」）**：保留 `procedure`/`editable`/版本信息 + **新增即时 `updateMeta(patch)` → `updateProcedure`（PATCH /procedures/{id}，meta-only）**。删除所有结构相关代码（见 D5/§删除）：chapters/steps 装载、`flatRows`/`chapterMap`/`stepMap`、dirty/`buildPayload`/`save`/`applyIdMap`/`validateForSave`、undo/redo、layer（`applyLayerRoles`/`layerRows`/`layerMode`/`toggleLayerMode`）、mark（`setMark`/`cycleMark`/`markMode`/`toggleMarkMode`/`applyAllMarks`/`markedNodes`）、转换（`convertToStep`/`convertToChapter`/`convertRootToStep`/`convertChapterToContent`/`splitChapterTitleContent`）、本地结构编辑（`addChapterNode`/`addStepNode`/`deleteNode`/`reorder`/`reorderWithin`/`moveCrossParent`/`updateChapterFields`/`updateStepFields`/`setStepKind`/`toggleSkip`/`toggleExpanded`）。
- 理由：`EditorTopBar`/`ProcedureDetailsPanel`/`AttachmentPanel`/版本历史仍读 `procedureEditor.procedure`/`editable`；保留一个 slim 元数据 store 比彻底退役更省、改动更局部。彻底退役留 B4 视情况。

### D3 — 顶栏改接（`EditorTopBar`）
- 删 **保存（Save）** 按钮（即时写，无 dirty）。
- **撤销** 改接 `nodeEditor.undo`/`canUndo`；**重做** 隐藏/禁用（`nodeEditor` 仅 undo，redo 字段预留未实现，母 spec 延后）。
- 加 **autosave 指示**「保存中…/已保存」（`$onAction` 计 `nodeEditor` mutating actions，逻辑从退役的 `NodeEditorView` 搬入）。
- **PDF 预览 / 发布 / 升级版本 / 丢弃 DRAFT / 复制为新程序 保留**（它们直接调 API，不依赖结构 store）。发布前若原有「待确认未清则阻断」逻辑，改读新树 `nodeEditor.reviewCount`（见 §保留并迁移）。

### D4 — 只读 `/view`
`NodeTreePanel`/`NodeDetailPanel` 增 `readonly` prop（由 `editable` 驱动，`editable = procedureEditor.editable`，`/view` → false、`/edit` 且 draft → true）。`readonly` 时：
- `NodeTreePanel`：隐藏行内 chip、多选 checkbox、γ 浮动条、新增/删除按钮、拖拽；仍可展开/折叠/选中/搜索/review 浏览。
- `NodeDetailPanel`：body 与 step 表单经 `RichTextEditor`/`StepFormFields` 只读渲染；隐藏 level/kind/skip 控件与 review 确认按钮。
- `RichTextEditor` 只读：实现期确认其只读/禁用形参（B3a-2 用 `variant='full'`；如无只读形参，传 `:readonly` 或 disabled 配置，必要时小幅补）。

### D5 — metadata 即时存
`ProcedureDetailsPanel` 在字段 change/blur → `procedureEditor.updateMeta(patch)`（乐观，`updateProcedure` PATCH）。删 dirty/Save/`save_procedure`。

### D6 — 拆分：B3b-1 切换 / B3b-2 删旧（各自合 main 绿、app 可用）
- **B3b-1（切换）**：去 gate、新面板接入 shell、`procedureEditor` 收窄 + `updateMeta`、只读模式、顶栏改接。合并后 app 完全跑新编辑器；旧结构代码**仍在但休眠**（不可达、不渲染）。merge 绿。
- **B3b-2（删旧）**：删全部旧结构代码 + 废测试 + `batchMark` 去 chapter-skip。merge 绿。
- 理由：切换必须先落地并验证，旧编辑器作为「可回退的休眠后备」存在一个中间态；验证通过后再删后备。两个绿色、app 可用的检查点，对齐 B3a-1/B3a-2 节奏。

---

## 组件/文件影响清单（带 file:line，实现以现网为准）

### 保留并改造
| 文件 | 改造 |
|---|---|
| `src/views/procedures/ProcedureEditorView.vue`（~420 行；gate 在 :32/:298，legacy v-else :299-396） | 去 gate；主体恒渲染 `NodeTreePanel`+`NodeDetailPanel`（绑 `nodeEditor`）+ 保留的 shell；onMounted 调 `nodeEditor.load` + `procedureEditor`（slim）取 meta；undo/autosave 逻辑并入；传 `readonly=!editable` 给新面板；删 legacy v-else 分支（B3b-2）。 |
| `src/components/editor/EditorTopBar.vue`（:1-54） | 删 Save；undo/redo 改接 `nodeEditor`（redo 禁用）；加 autosave 指示；其余按钮保留。 |
| `src/store/procedureEditor.ts`（1078 行） | 收窄为元数据 store：保留 `procedure`/`editable`/版本 + 新增 `updateMeta`；删 D2 列出的全部结构/save/layer/mark/转换/本地编辑代码（B3b-2 主体删除；B3b-1 只新增 `updateMeta` + 让结构代码停止被调用）。 |
| `src/components/editor/ProcedureDetailsPanel.vue` | 字段 change/blur → `updateMeta`（即时）；删 dirty/Save 依赖。 |
| `src/components/editor/NodeTreePanel.vue`、`NodeDetailPanel.vue` | 增 `readonly` prop + 只读分支（B3b-1）。 |
| `src/utils/batchMark.ts`（chapter-skip 在 :48） | 删 `if (r.kind === 'chapter') continue` 及已 moot 的 cascade chapter 逻辑（B3b-2）。 |

### 删除（B3b-2）
- 组件：`ChapterTreePanel.vue`（619 行）、`TreeRow.vue`、`ChapterDetailPanel.vue`、`ContentDetailPanel.vue`、`StepDetailPanel.vue`、`views/procedures/NodeEditorView.vue`（退役）。
- utils：`layerMark.ts`（202 行，含 `LayerRole`/`LayerRow`/`LayerUpdate`/`defaultLayerRole`/`effectiveRole`/`computeLayerUpdates`/`validateLayerQ25`/`computeLayerIndents`/`roleLevel`/`setHeadingContext`）。
- store：`procedureEditor.ts` 的 D2 结构/save/layer/mark/转换/本地编辑 actions+getters（含 `buildPayload`/`save`/`applyIdMap`/`validateForSave`/`isDirty`/`resetEditState`/undo/redo/`pushUndo`）。
- API（前端）：`api/procedures.ts` 的 `saveProcedure()`（:52-60）调用点（`ProcedureEditorView` doSave、`procedureEditor.save`）。后端 `PUT /procedures/{id}` 端点删除留 B4。
- 测试：`ChapterTreePanel.spec.ts`、`TreeRow.spec.ts`、`ChapterDetailPanel.spec.ts`、`ContentDetailPanel.spec.ts`、`utils/layerMark.spec.ts`、`store/procedureEditor.applyLayerRoles.spec.ts`、标记模式相关 spec、`NodeEditorView.spec.ts`（退役；有价值断言并入 `ProcedureEditorView` 集成测试）。
- 注：`reviewNav.ts` **保留**（新树用）；`EditorTopBar.spec.ts` **改不删**（Save 移除、undo 改接）；`batchMark.spec.ts` 改（去 chapter-skip 用例 + node 行用例留）。

### 保留并迁移
- `review` 待确认全链路已在 `NodeTreePanel`（徽章/`reviewCount`/`reviewOnly` 过滤/下一个/`confirmReview`）。**校验**发布流程是否有「待确认未清阻断发布」并改读 `nodeEditor.reviewCount`（实现期核对 `EditorTopBar`/publish 处理；若原无此阻断则不新增）。
- `batchMark.ts`：`buildSelection` 已在 B3a-2 放宽为结构型 `SelectableRow`；B3b-2 去 chapter-skip 即收口。

---

## 数据流

- 加载：`ProcedureEditorView` onMounted → `nodeEditor.load(id)`（结构）+ slim `procedureEditor` 取 `procedure`/`editable`（meta）。
- 结构编辑（editable）：行内 chip/γ 浮动条/create/delete/拖拽/body/step 表单/review 确认 → `nodeEditor` 即时 node API（B3a-2 既有）。撤销 → `nodeEditor.undo`（顶栏按钮）。
- 元数据编辑（editable）：`ProcedureDetailsPanel` change/blur → `procedureEditor.updateMeta` → `updateProcedure` PATCH（即时·乐观）。
- 生命周期：发布/升级/丢弃/复制/PDF → `ProcedureEditorView` 直调既有 API（不变）。
- 只读（/view，editable=false）：新面板 readonly 渲染；无写路径。

## 错误处理
- 结构写错误：`http` 拦截器 toast（B3a-2 既有）；颗粒度写各自乐观，per-node revision 冲突按既有处理。
- 元数据写错误：`updateProcedure` 失败 toast；乐观回滚到上次值（实现期定）。
- meta 取失败：不阻塞结构编辑（面包屑空，B3a-2 既有容错搬入）。

## 测试策略（vitest）
- **B3b-1**：
  - `ProcedureEditorView` 集成：无 gate 恒渲染 `NodeTreePanel`+`NodeDetailPanel`；onMounted 调 `nodeEditor.load`；`/view`（editable=false）→ 面板 readonly。
  - `NodeTreePanel`/`NodeDetailPanel` readonly：隐藏编辑控件、body/form 只读。
  - `EditorTopBar`：undo 调 `nodeEditor.undo`、无 Save、autosave 指示随 `$onAction` 翻转。
  - `ProcedureDetailsPanel`：字段改 → `updateMeta`（即时，不经 save_procedure）。
  - `procedureEditor.updateMeta`：调 `updateProcedure` payload + 乐观。
- **B3b-2**：删废测试随其 subject；`batchMark` 去 chapter-skip 后 node 行选择仍对；全量回归确认无悬挂引用。
- 每阶段：全 vitest 绿、`vue-tsc --noEmit` 干净、改动文件 eslint 干净；`running-smartsop-dev` 手动验 **`/edit`（可编辑）与 `/view`（只读）** 两条路由；后端 `pytest` 不受影响（B3b 纯前端）。

## 范围边界与延后
- **B3b 纯前端**：node API（Plan A）+ `updateProcedure`（既有）已在；零后端改动。
- **延后 B4**：后端死端点删除（`save_procedure`/`apply-marks`/`apply-layer-roles`/`convert_to_*` + 相关 schema + `GET /procedures/{id}` 的 chapters/steps 装配）；停双写 + 删旧表 + `numbering_service`/`node_sync`/`chapter_service` + 重建 dev.db。
- **延后纯增量 pass**：β 键盘（`Cmd+1..4`/`Tab`；注 redo）、δ markdown、redo、虚拟列表、级联多选、跨标签 412 精修、heading 多段 body「引言」编辑 nicety。
- **本期不做**：彻底退役 `procedureEditor`（slim 保留）；为新面板加键盘快捷键。

## 风险与注意
- **dev.db 陈旧**：现有程序多为 0 个 `ProcedureNode`（B2a 起仅结构写触发 recompute 才 rebuild）。切换后打开未 rebuild 的程序 → 空树。手动验收需用有 node 的程序或先触发一次结构写/rebuild；B4 整体重建 dev.db。验收时记录此点，勿误判为 bug。
- **双 store 过渡态**：`nodeEditor`（结构）+ slim `procedureEditor`（meta）并存，可接受；B4 视情况进一步合并。
- **B3b-1 中间态**：旧结构代码休眠但仍在树/打包内；B3b-2 删除前确保新编辑器经手动验收（含 /view）。
- **只读富文本**：实现期确认 `RichTextEditor` 只读形参；缺则小幅补（不扩散到其它调用点）。

## 子计划与顺序
1. **B3b-1（plan 待写）**：切换 + 集成 + slim store/`updateMeta` + 只读 + 顶栏改接 + vitest。合 main 绿、app 跑新编辑器（旧码休眠）。
2. **B3b-2（plan 待写）**：删旧组件/utils/store 死码/前端 save_procedure 调用/废测试 + `batchMark` 去 chapter-skip + vitest 全量回归。合 main 绿、旧结构代码清除。

每子计划合并前：前端全测绿、`vue-tsc`/eslint 干净、`/edit` 与 `/view` 手动验收、后端不受影响。
