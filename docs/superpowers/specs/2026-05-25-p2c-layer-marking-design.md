# P2c · 批量层级标定（4 选项）设计

**日期：** 2026-05-25
**状态：** 已批准
**作者：** 协作设计（cui_yuming + Claude）
**上位文档：** `2026-05-25-unified-create-edit-model-overview-design.md`（北极星）；P2 拆为 P2a/P2b/P2c，本文是 **P2c**。

---

## 1. 背景与决定（两层拆分 A）

探明编辑器结构机制后确认：5 个角色里，**一级/二级/三级/正文**都在章节表内部，靠改 `parent_id`/`content_type` 实现——**一次批量保存即可、保 id、零丢失、不触发 Q25**；而**步骤**是跨实体（章节表↔步骤表）、换 id、有损（步骤→章节丢表单/确认/附件标记，且无藏存）、并受 **Q25 互斥**（一个父级下章节/正文 与 步骤 不能混）。编辑器**已有**步骤标记模式（mark-mode + apply-marks）妥善处理 Q25 与 content→steps 拆分。

**决定（A）：**
- 新建**批量 4 选项"层级标定"视图**（一级/二级/三级/正文）——解决用户真正的批量痛点（解析层级/标题-正文大面积出错）。
- **步骤维持现有 mark-mode + apply-marks 不动**；两者可同处一个"层级标定"入口下作为两个子模式（UX 连贯，机制各自独立）。
- **降型藏存暂缓**：步骤↔章节互转回归"刻意的逐节点动作"，误降风险低，本期不做藏存 schema。

**非目标：** 5 角色合一的原子批量端点；降型藏存字段/端点；改动现有步骤 mark-mode/apply-marks 语义；P3 入口统一与下线。

## 2. 关键现状（探查确认）

- 批量保存 `editor_service.save_procedure`：一次 PUT 可同时改 `parent_id`、`content_type`(章节↔正文)、`sort_order`、增删；**`level` 由服务端重算**；最终态校验 Q25 / content 叶子 / ≤3 级 / 父引用有效 / 无环。**不能**跨表转换（章节↔步骤只能走 convert 端点）。
- 本地结构动作（`toggleContentType` 等）改状态、置脏、可撤销、随 save 持久化、**保 id**。
- `ImportMarkingRow.vue`（import-v2）：props `{label, role, indent}`、emit `set`、4 选项 `LayerRole = chapter_1|chapter_2|chapter_3|content`——正是所需选择器，可复用。
- `importTree.ts`：`buildTreeFromRoles`/`computeMarkIndents`/`defaultRoleOf` 是 beta2 的 l1/l2/l3 走位逻辑，但输出嵌套 `WizardNode`；编辑器需要**扁平 `EditorChapter` 更新**，故另写编辑器版纯逻辑（复用算法思路）。
- 编辑器 `store.flatRows` 文档序；`store.chapters`/`store.steps` 扁平；`store.markMode` 是步骤标记模式开关；`ChapterTreePanel` 渲染树/虚拟滚动。

## 3. 决定细则

### D1 · 层级标定模式（4 选项）
- 新增编辑器状态 `layerMode`（与步骤 `markMode` 互斥；同一"层级标定"入口下切换两个子模式）。
- 开启时，树面板渲染**章节/正文节点的扁平文档序清单**（步骤不在清单里——见 D4），每行用 `ImportMarkingRow` 给 4 选项（一级/二级/三级/正文），**预填当前角色**：章节按当前 `level` → chapter_1/2/3（>3 夹到 chapter_3）；正文 → content。

### D2 · 应用 = 本地原地重排 + 随正常保存
- 「应用层级」时：用纯逻辑 `layerMark.ts` 由 `(文档序行, roleMap)` 算出每个节点的目标 `{parent_id, content_type, sort_order}`（沿用 l1/l2/l3 走位 + 不可达层级夹紧 + content 作叶子）。
- **`pushUndo()` 后本地写入** `EditorChapter`（改 `parent_id`/`content_type`/`sort_order`，**保 id**），置脏；退出层级模式。
- 由编辑器正常 `save()`（批量 PUT）持久化，服务端重算 `level` 并校验。**可撤销、零丢失、保 id**。

### D3 · 纯逻辑 `layerMark.ts`（可单测）
- `defaultLayerRole(chapter, level)`：章节→`chapter_${clamp(level,1,3)}`；content→`content`。
- `computeLayerUpdates(rows, roleMap)`：输入文档序的 `{id, hasStepChildren}` 行 + roleMap，输出 `Map<id, {parent_id: string|null, content_type, sort_order}>`。走位：维护 l1/l2/l3 最近章节指针；chapter_2 无 l1 → 夹到根；chapter_3 无 l2 → 挂 l1/根；content 挂最近章节指针、`content_type='content'`；sort_order 按新父级内顺序。

### D4 · 步骤在层级视图里的处理
- 步骤**不参与** 4 选项清单（它们由独立的步骤 mark-mode 处理）；在层级视图中**只读随行**或隐藏，其 `chapter_id` 不变（父章节只是被重排/改级，仍存在）。
- **含步骤子节点的章节**：其"正文"选项**禁用**（content 必须是叶子且 Q25 不允许 content/章节与步骤混在同一父级）。`ImportMarkingRow` 增加可选 `disableContent` prop（或在编辑器侧包一层禁用）。

### D5 · 步骤标记模式保持不变
- 现有 mark-mode（勾选→标步骤/正文→apply-marks）与 apply-marks 语义**不动**。仅在入口处与"层级标定"并列/切换。

## 4. 数据流

1. 进编辑器（已可见待确认/预览，P2a/P2b）。
2. 开「层级标定」→ 4 选项扁平清单（预填当前层级）。
3. 批量改若干行角色 → 「应用层级」→ 本地原地重排（保 id、置脏、可撤销）→ 退出模式。
4. 正常保存（Ctrl+S / 保存）→ 批量 PUT 持久化，服务端重算 level + 校验。
5. 步骤维度仍走独立的步骤 mark-mode（不变）。

## 5. 边界与错误

- **不可达层级**：用户把某行标 三级 但其上无 二级 → 走位时夹到可达层级（不报错，所见即所得后由保存重算）。
- **正文含子**：含步骤子节点的章节禁用"正文"；含章节/正文子节点的章节若被标"正文"→ 走位时其子节点改挂到最近的上层章节（content 作叶子），不产生非法树。
- **空树 / 无章节**：层级清单为空，「应用」无操作。
- **撤销**：应用前 `pushUndo()`，可一键撤销整次重排。
- **保存校验失败**（理论上算法已保证合法）：保留脏态、拦截器提示，不静默。

## 6. 测试

- 前端纯逻辑 `layerMark.spec.ts`：`defaultLayerRole`；`computeLayerUpdates` 覆盖 一级/二级/三级/正文 组合、不可达层级夹紧、content 作叶子、含子章节被标正文时子节点改挂。
- store：`applyLayerRoles(roleMap)` 写入 `parent_id`/`content_type`/`sort_order` + 置脏 + pushUndo；`layerMode` 切换与 `markMode` 互斥。
- 组件：层级模式下渲染 `ImportMarkingRow` 扁平清单、预填角色、`disableContent`（含步骤子节点）、「应用」调 store。
- Gate：前端 `lint+typecheck+test+build`。（P2c 主要是前端；如复用 `ImportMarkingRow` 不改后端。）

## 7. 文件清单（预估）

- 新建 `frontend/src/utils/layerMark.ts` + `frontend/tests/unit/utils/layerMark.spec.ts`。
- 改 `frontend/src/store/procedureEditor.ts`：`layerMode` 状态 + `toggleLayerMode` + `applyLayerRoles(roleMap)`（用 layerMark 计算 + 本地写入 + pushUndo + 置脏）+ 与 markMode 互斥。
- 改 `frontend/src/components/editor/ChapterTreePanel.vue`：层级模式分支渲染扁平 `ImportMarkingRow` 清单 + 入口切换 + 「应用层级」。
- 可能改 `frontend/src/components/import-v2/ImportMarkingRow.vue`：加可选 `disableContent` prop（向后兼容）。
- 相应单测。

## 8. 前向提醒（P3）

P2a 已让编辑器复用 `WordPreviewPanel`、`ImportSideRail`；P2c 再复用 `ImportMarkingRow`（及 importTree 算法思路）。**P3 下线 beta2 时，这些被编辑器复用的组件不可删**，应迁到共享目录（如 `components/shared/` 或 `components/editor/`）。本期先复用 + 标记，迁移在 P3 处理。

## 9. 留给后续

- 降型藏存（步骤↔章节无损 round-trip）：若日后步骤进入批量视图或需无损互转再做。
- 5 角色合一（含原子批量端点）：A 方案下不做；如未来 UX 要求再评估。
- P3：入口统一（空白/从 Word）、下线 beta2 + 老导入、共享组件迁移、灰度。
