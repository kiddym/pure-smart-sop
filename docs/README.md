# Smart SOP 文档索引

本目录是 Smart SOP 项目的全部规范、设计与运维文档。所有团队成员在开始任何开发任务前应先阅读相关文档。

## 文档分类

### 一、项目纲领与决策

| 文档 | 用途 | 适用人群 |
|------|------|--------|
| [development-plan.md](development-plan.md) | 项目整体路线图、阶段划分、里程碑、风险 | 全员 |
| [feature-clarifications.md](feature-clarifications.md) | **三轮 grill 决策汇编 — 业务语义权威来源** | 全员（必读）|
| [data-model.md](data-model.md) | 完整数据模型与 ER 关系 | 后端、DBA |
| [editor-behavior.md](editor-behavior.md) | 编辑器行为规范（标记/转换/撤销/编号/约束）| 前端（必读）、后端（参考） |
| [pdf-rendering.md](pdf-rendering.md) | PDF 渲染规范（封面/TOC/修订/内容/特殊元素/字体）| 后端（必读）、前端（参考） |

### 二、开发规范

| 文档 | 用途 | 适用人群 |
|------|------|--------|
| [backend-coding-standards.md](backend-coding-standards.md) | Python / FastAPI 代码风格、目录、错误处理、日志 | 后端 |
| [frontend-coding-standards.md](frontend-coding-standards.md) | Vue 3 / TypeScript 代码风格、组件、Pinia、API 层 | 前端 |
| [api-specification.md](api-specification.md) | RESTful API 设计原则、统一响应、错误码、接口清单 | 全员 |
| [database-specification.md](database-specification.md) | 表 / 字段 / 索引 / 迁移命名规范 | 后端、DBA |

### 三、协作规范

| 文档 | 用途 | 适用人群 |
|------|------|--------|
| [git-workflow.md](git-workflow.md) | 分支策略、Commit 规范、PR 流程 | 全员 |
| [testing-standards.md](testing-standards.md) | 测试金字塔、覆盖率要求、命名规范 | 全员 |

### 四、运维与部署

| 文档 | 用途 | 适用人群 |
|------|------|--------|
| [deployment.md](deployment.md) | 本地 / Docker / 生产部署、环境变量、备份恢复 | 后端、运维 |

## 阅读建议

| 角色 | 必读顺序 |
|------|---------|
| 后端开发 | development-plan → **feature-clarifications** → data-model → api-specification → **pdf-rendering** → backend-coding-standards → database-specification → testing-standards → git-workflow |
| 前端开发 | development-plan → **feature-clarifications** → **editor-behavior** → api-specification → frontend-coding-standards → testing-standards → git-workflow |
| 新人入职 | README → development-plan → feature-clarifications → 自身角色规范 → git-workflow |
| 运维 | deployment → database-specification |
| 产品 / PO | development-plan → feature-clarifications |

## 文档维护原则

1. **任何代码变更涉及规范偏离，必须先修改文档再写代码**，避免规范与实现脱节
2. 每个 PR 若涉及对外接口变更，必须同步更新 [api-specification.md](api-specification.md)
3. 每次数据库结构变更，必须同步更新 [data-model.md](data-model.md) 并附 Alembic migration
4. 业务语义争议时，[feature-clarifications.md](feature-clarifications.md) 为**最高权威**
5. 文档使用 Markdown，统一中文；技术术语首次出现用「中文（English）」双语标注
6. 文档变更需经过 PR 评审，与代码同样标准

## 缺失文档清单

以下文档将在对应阶段补齐：

- `architecture.md` — 架构图（Phase 1 完成后补）
- `security.md` — 安全清单（上线前补）
- `changelog.md` — 变更日志（首次发版补）
- `operations-runbook.md` — 运维手册（上线前补）

## 决策追溯

如果你在代码评审 / 实现中对某个功能行为有疑问，按以下顺序追溯：

```
1. feature-clarifications.md     ← 最权威，含完整决策依据
2. data-model.md / api-specification.md / editor-behavior.md / pdf-rendering.md  ← 落地规范
3. development-plan.md           ← 阶段范围与优先级
4. 06-程序管理模块功能说明.md     ← 原 spec（已被上述文档覆盖与修正）
```
