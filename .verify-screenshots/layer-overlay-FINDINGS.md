# Layer-Mode Tree Overlay — MCP Verification 实测发现

**日期：** 2026-05-27  
**Branch：** `worktree-feat+layer-mode-tree-overlay` HEAD `8ccae04`  
**Procedure：** `712623c4-a5e2-4775-a8ae-323266af06f6` (内容块降级验证)  
**入口：** `localhost:5174/procedures/712623c4-…/edit`（worktree frontend）+ 主仓 backend on `:8000`

## 验证场景

### ✅ A. 视图统一：layer 模式 = TreeRow 叠加层（不再走独立替换视图）

进入「层级标定」后：
- 旧的 `<EditorLayerMarking>` 独立面板不再出现（已删）
- 完整的 chapter + step + content 树都渲染（与 mark mode 渲染模型对齐）
- 每行右侧有 role picker

screenshot: `layer-overlay-01-mode-entered.png`

### ✅ B. 角色选项按行类型差异化

| 行类型 | 选项 | 备注 |
|---|---|---|
| chapter (无叶子) | 一级 / 二级 / 三级 / 正文 | 全部可用 |
| chapter (有叶子) | 一级 / 二级 / 三级 / ~~正文~~ | 正文 disabled（有 step/content 子，不能降为 content） |
| step | 保持 / 一级 / 二级 / 三级 | 全部可用 |
| content | 保持 / ~~一级~~ / ~~二级~~ / ~~三级~~ | chapter_X disabled（Phase 1 限制，后端拒绝 content→chapter） |

content 行禁用 chapter_X 与 Plan 一致：后端 `CONTENT_BLOCK_NOT_CONVERTIBLE`，Phase 1 在 UI 层先挡住。

screenshot: `layer-overlay-01-mode-entered.png`

### ✅ C. Live indent 预览生效

把 step "操作总述正文C" (2.1) 选为 二级：

| 行 | apply 前 padding | apply 前 indent | 选 C=二级 后 padding | 选后 indent |
|---|---|---|---|---|
| 操作总述正文C (2.1) | 22px (L1 下) | 1 | 22px (新 L2) | 1 |
| 操作注意事项正文D (2.2) | 22px (L1 下) | 1 | **38px** (新 L2 下) | **2** |

D 的缩进自动跟随 C 提升后的标题上下文，无需重渲染整树——`computeLayerIndents` 实时算缩进的 live preview UX 正常。

screenshot: `layer-overlay-02-step-promoted-live-preview.png`

### ✅ D. 简单提升：完整端到端跑通

把 step "收尾正文E" (3.1) 提升为 二级 + 点「应用层级」：

apply 前 DB 状态：
```
收尾 (chapter L1)
  └── E (step kind, content="<p>收尾正文E。</p>")
```

apply 后 DB 状态（curl 验证）：
```
收尾 (chapter L1)
  └── 未命名章节 (chapter L2, new id 55b35d8f-…)
        └── (content step, content="<p>收尾正文E。</p>")
```

UI 行从 `☐ 3.1 收尾正文E。` 变成 `📘 3.1 未命名章节`，缩进 22px (L2)。layer mode 自动退出。

**这就是用户原始诉求**——"在章节下面的内容中，发现了没有被解析出来的二级标题"——的简单形态。

screenshot: `layer-overlay-05-simple-promote-success.png`

### ⚠️ E. 已发现的实测 GAP — 同级叶子未被前端 Q25 dry-run 捕获

#### 场景

`操作步骤` (L1) 下有两个 step 兄弟：`操作总述正文C` (2.1) 和 `操作注意事项正文D` (2.2)。

把 C 选为 二级 + 应用：

#### 预期 vs 实际

| 阶段 | 期望 | 实际 |
|---|---|---|
| 前端 `validateLayerQ25` 校验 | 报冲突（C 升 chapter，D 留 leaf，同父） | **无冲突**（dry-run 假定 D 跟随 C 重挂到新 L2） |
| 后端 `convertStepToChapter(C)` | 拒绝（SIBLING_TYPE_CONFLICT） | **拒绝 400** |
| 用户感知 | Q25 banner 列出冲突 | **静默失败**——按钮无反馈，console 一行未处理 Promise rejection |

screenshot: `layer-overlay-03-q25-conflict-banner.png` (banner 未出现) + `layer-overlay-04-backend-400-gap.png` (无可见反馈)

#### 根因

前端 `computeLayerUpdates` 按文档序 walk，把"提升 C 后的所有同级叶子 D"算到新章节 C 下（`leaf-reparent: parent_id=C`）。`validateLayerQ25` 按这套结果分组，所以 `操作步骤` 那一组里只看到 chapter C（D 已被算去 C 名下），不报混合。

后端 `convertStepToChapter(C)` 是单行 API：把 C 这一行转成章节，不动 D 的 chapter_id。完成后 `操作步骤` 在 DB 里的孩子是 `[新章节 C, step D]`——**混合**，触发 SIBLING_TYPE_CONFLICT。

也就是：**dry-run 的"理想最终态"和 backend 单步 API 的"实际过渡态"不一致**。Plan 的 "Risks & known gotchas" 提到过这个边角情况，但实测看下来这是用户**最常见**的场景（凡是父章节下有 ≥2 个叶子就触发），不是边角。

#### 候选修法（留给用户决策）

1. **校验器修正**（推荐）：`validateLayerQ25` 接收每个 leaf row 的原始 `chapter_id`，在分组时把每条 leaf 同时记到「dry-run 目标父」和「DB 原父」两个 bucket，发现 DB 原父出现混合就报 Q25 冲突。需要扩展 `LayerRow` 加 `originalParent` 字段或单独传 map。
2. **批量 API**：后端新增 `POST /procedures/:id/apply-layer`，原子地把整个 roleMap 应用到 DB。彻底消除前后端语义错位。改动量大。
3. **客户端编排**：前端在 `convertStepToChapter` 前先 PATCH 同级 leaf 的 chapter_id 到新章节，凑出合法过渡。多次 API 调用，半事务，错误处理复杂。

短期止血：在 `applyLayer` 里 try/catch 后端 400 错误并 toast 给用户，让"静默失败"变成"明确失败"。

## 单元/集成测试基线

`cd frontend && npx vitest run` → **355 passed (40 files)**, 1 pre-existing EP/jsdom 警告。Lint clean。

## 服务器留存

- worktree frontend: `localhost:5174`（仍运行；进程在 `/tmp/frontend.log`）
- 主仓 backend: `localhost:8000`（用户的；未由我启动）
