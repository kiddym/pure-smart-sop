# SmartSOP 前端「身份整合」设计 Spec

- 日期：2026-05-24
- 范围：身份整合（Identity pass）
- 字体策略：自托管西文显示字 + 中文系统字
- 状态：已通过设计评审，待 spec 复核

---

## 1. 背景与问题

前端（Vue 3 + Element Plus + Tailwind）已存在一套有观点的**暖色身份**，但只贯彻了一半：

- `src/assets/styles/tokens.css` 定义了暖盘：赤陶 `--accent: #d97757`、米色 `--bg-surface: #f5f3ef`、暖近黑 `--text-primary: #1a1714`，以及状态暖盘（鼠尾草绿等）。
- 应用外壳 `src/layouts/AppLayout.vue` 正确使用了暖盘（米色侧栏、赤陶高亮菜单、暖主区）。
- **但内容页与基础配置仍是 Element Plus 蓝灰默认**：
  - `tailwind.config.js` 的 `primary = #409eff`（Element 蓝）。
  - `main.css` body 背景 `#f5f7fa`、文字 `#303133`（Element 冷色默认）。
  - 全仓 **19 处硬编码 `#409eff/#337ecc`**、**145 处内联 hex**。
  - 主列表页 `ProcedureLibraryView.vue` 未使用任何 token，全是原厂蓝按钮。
- `tokens.css` 注释声称权威来源是 `docs/design-system.md`，但该文件不存在（悬空引用）。
- 排版无性格：全程系统字体（PingFang SC / YaHei / Helvetica / Arial），标题仅靠字号区分。
- 几乎无动效（全仓仅 2 处 `transition:`）。

结论：项目躲过了「AI 营销垃圾风」，却落入「默认后台模板风」。本次目标是把已有的身份种子**打通到全应用**。

## 2. 目标 / 非目标

### 目标
1. 暖色身份贯穿全应用，消除蓝灰双轨冲突。
2. Element Plus 主题色统一为赤陶梯度，组件自动继承。
3. 标题/品牌获得字体性格（西文显示字），正文保持系统中文字。
4. 关键场景补轻量、克制、可访问的动效。
5. 修复设计治理悬空引用，建立名副其实的单一来源文档。

### 非目标（YAGNI，本次明确排除）
- 暗色模式。
- 页面信息架构 / 构图重构。
- 背景质感 / 噪点纹理 / 渐变网格。
- 完整动效编排系统。
- 中文 web 字引入与子集化。

## 3. 技术决策

### 3.1 Element 主题色覆盖 —— `:root` 变量层（不重编译 SCSS）

`src/main.ts` 的加载顺序为：`element-plus/dist/index.css` → `tokens.css` → `main.css`。因此在 `main.css` 的 `:root` 覆盖 Element 的 CSS 变量即可在不重编译 SCSS 的前提下全局生效。多个组件已在引用这些变量（带蓝色 fallback），覆盖后会自动变暖：

- `src/components/editor/TreeRow.vue`（拖拽高亮：`--el-color-primary-light-9` / `-light-8` / `--el-color-primary`）
- `src/components/import/ModeStep.vue`（选中边框：`--el-color-primary`）
- `src/components/import/UploadStep.vue`（链接色：`--el-color-primary`）

赤陶梯度（基于 `#d97757`，按 Element「与白/黑混合」规则计算）：

```css
:root {
  --el-color-primary:          #d97757;
  --el-color-primary-light-3:  #e4a089; /* +30% white */
  --el-color-primary-light-5:  #ecbbab; /* +50% white */
  --el-color-primary-light-7:  #f4d6cd; /* +70% white */
  --el-color-primary-light-8:  #f7e4dd; /* +80% white */
  --el-color-primary-light-9:  #fbf1ee; /* +90% white */
  --el-color-primary-dark-2:   #ae5f46; /* +20% black */
}
```

> 说明：success/warning/danger 暂保留 Element 默认（`PublishChecklistDialog.vue`、`FormFieldPreview.vue` 在用），避免扩大回归面；如评审要求暖化可后续单列。本次仅统一 primary。

### 3.2 双轨收敛

- `tailwind.config.js`：`primary.DEFAULT` 由 `#409eff` → `#d97757`，`primary.dark` 由 `#337ecc` → `#ae5f46`。
- `main.css` body：背景 `#f5f7fa` → `var(--bg-surface)`；文字 `#303133` → `var(--text-primary)`。
- 清理硬编码蓝：
  - 能映射到 Element 变量的 → 改用 `var(--el-color-primary*)`（去掉裸 hex fallback 或保留与梯度一致的 fallback）。
  - 其余蓝色装饰 → 替换为暖盘 token。
  - 收口检查：`grep -rn "#409eff\|#337ecc" src` 应为 0。
- `tokens.css` 升格为权威单一来源：纳入 Element 赤陶梯度别名、字体变量，集中管理。

### 3.3 字体 —— 自托管 Fraunces（西文显示）+ 中文系统字

- 选 **Fraunces**（opsz 可变衬线，有性格，契合「文档/程序」气质；刻意避开技能点名的 Space Grotesk，避免趋同）。
- 自托管：拉丁子集 woff2，1–2 个字重（如 500 / 600），放 `src/assets/fonts/`，经 `@font-face` 引入，`font-display: swap`。
- **降级策略**：实现时若因网络/代理拉不到字体文件，回退系统衬线栈 `Georgia, 'Times New Roman', serif`，不阻塞交付。
- 应用范围：仅品牌字 `.app-brand` 与页面标题 `h2/h3`（程序库标题、各 View 标题）。正文中文继续用苹方/系统栈。
- 变量化：在 tokens.css 定义 `--font-display: 'Fraunces', Georgia, 'Times New Roman', serif;`，tailwind `fontFamily.display` 引用之。

### 3.4 轻量动效（克制 + 可访问）

全部 CSS-only，统一包裹在 `@media (prefers-reduced-motion: reduce)` 下可关闭：

1. **路由切换**：`AppLayout.vue` 的 `<RouterView>` 用 `<Transition name="fade">` 包裹，120–160ms 淡入淡出。
2. **入场 stagger**：主列表 / 向导树首屏一次性 staggered 淡入（`animation-delay` 递增，仅入场一次，不循环）。
3. **向导步骤**：导入向导步骤切换补轻量 slide/fade。
4. **对话框**：沿用 Element 自带 fade+zoom，不改。
5. `main.css` 增加可复用动效基类（如 `.u-fade-in`）与 `prefers-reduced-motion` 兜底。

### 3.5 修复治理悬空引用

新建 `SmartSOP/frontend/docs/design-system.md`，内容覆盖：
- §1 身份概述（暖盘理念）
- §2 色彩：暖盘 token、Element 赤陶梯度映射表、状态色语义
- §3 字体：显示字 + 中文系统字策略、变量
- §4 动效：原则、时长、reduced-motion
- §5 治理：禁止散落 hex，新增配色先回填本文档

使 tokens.css 注释中的「权威见 docs/design-system.md」名副其实。

## 4. 交付物清单（按文件）

| 类型 | 文件 | 变更 |
|---|---|---|
| 改 | `src/assets/styles/main.css` | `:root` Element 赤陶覆盖；body 暖化；动效基类 + reduced-motion |
| 改 | `src/assets/styles/tokens.css` | 扩为权威 token：Element 梯度别名 + 字体变量 |
| 改 | `tailwind.config.js` | `primary` 暖化；`fontFamily.display` |
| 新增 | `src/assets/fonts/` + `@font-face` | Fraunces woff2（拉丁子集，含系统衬线降级） |
| 改 | `src/layouts/AppLayout.vue` | `<RouterView>` 过渡；品牌字应用 |
| 改 | 约 6–8 个含硬编码蓝的组件 | 替换为 token / Element 变量 |
| 新增 | `SmartSOP/frontend/docs/design-system.md` | 单一来源设计文档 |

## 5. 验证

- `npm run build`（vue-tsc --noEmit && vite build）通过。
- `npm run lint`（eslint --max-warnings 0）0 警告。
- `grep -rn "#409eff\|#337ecc" src` 结果为 0。
- 启动前端（5173）截图走查：主列表 / 编辑器 / 导入向导，确认无残留蓝色、显示字与动效生效、reduced-motion 下动画关闭。

## 6. 风险与缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| 改 Element primary 后个别"默认蓝才好看"处需微调 | 低 | 截图走查时逐一确认 |
| 字体文件受代理影响拉不到 | 中 | 系统衬线栈降级，不阻塞 |
| 硬编码色替换漏网 | 中 | grep 收口 `#409eff/#337ecc` 为 0 |
| success/warning/danger 仍为冷色，与暖 primary 略不协调 | 低 | 本次明示保留，按需后续单列 |
