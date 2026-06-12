# SmartSOP 前端设计系统（单一来源）

> 权威配色/字体/动效以本文档为准。新增配色必须先回填本文档，禁止在组件里散落 hex。
> 令牌实现见 `src/assets/styles/tokens.css`。

## §1 身份概述

暖色身份：以赤陶（terracotta）为强调、鼠尾草绿表"已发布"、米色为壳层背景，
传达"文档/程序/合规"的克制、可信气质。刻意避开默认后台模板的蓝灰。

## §2 色彩

### 2.1 壳色与强调
| Token | 值 | 用途 |
|---|---|---|
| `--accent` | `#d97757` | 强调（赤陶） |
| `--folder-amber` | `#d9a14e` | 程序库文件夹引导图标（暖琥珀，亮暗通用） |
| `--bg-surface` | `#f5f3ef` | 壳层背景（米） |
| `--bg-elevated` | `#eceae5` | 抬升面 |
| `--text-primary` | `#1a1714` | 主文字（暖近黑） |

### 2.2 Element Plus 主题色映射（赤陶梯度）
在 tokens.css 的 `:root` 覆盖，自动级联全组件：

| 变量 | 值 |
|---|---|
| `--el-color-primary` | `#d97757` |
| `--el-color-primary-light-3` | `#e4a089` |
| `--el-color-primary-light-5` | `#ecbbab` |
| `--el-color-primary-light-7` | `#f4d6cd` |
| `--el-color-primary-light-8` | `#f7e4dd` |
| `--el-color-primary-light-9` | `#fbf1ee` |
| `--el-color-primary-dark-2` | `#ae5f46` |

> success / warning / danger 暂保留 Element 默认（已被 PublishChecklistDialog
> 等使用），如需暖化后续单列。

### 2.3 状态色语义
| Token | 值 | 语义 | 视觉 |
|---|---|---|---|
| `--st-draft` | `#a89a86` | 草稿 | 空心暖灰点 |
| `--st-published` | `#88b07a` | 已发布 | 实心鼠尾草绿 |
| `--st-archived` | `#6b635a` | 已归档 | 暗实心 |
| `--st-deprecated` | `#d9685e` | 废弃 | 警示红 |

## §3 字体

- 标题/品牌：`--font-display` = `'Fraunces', Georgia, 'Times New Roman', serif`
  （西文显示衬线；自托管 woff2，拉丁子集；拉取失败降级系统衬线）。
- 正文：系统字栈 `PingFang SC, Microsoft YaHei, Helvetica Neue, Arial, sans-serif`。
- 应用：全局 `h1/h2/h3/.app-brand` 用显示字；正文中文保持系统字。

## §4 动效

- 原则：克制、一次性入场、尊重 `prefers-reduced-motion`。
- 路由切换：`<Transition name="fade">`，160ms 淡入淡出。
- 首屏：`.u-fade-in` keyframe，280ms，仅入场一次。
- 对话框：沿用 Element 自带 fade+zoom。

## §5 治理

- 禁止在 `.vue`/`.css` 中写裸 hex 配色；一律走 `var(--*)`。
- 新增配色 → 先回填本文档 §2 → 再在 tokens.css 落地。
- CI/复查：`grep -rn "#409eff\|#337ecc\|#ecf5ff\|#d9ecff" src` 应为 0。
