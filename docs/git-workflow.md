# Git 工作流（Git Workflow）

> 适用于所有 Smart SOP 仓库的协作流程。

## 1. 分支模型

采用 **GitHub Flow** 简化变体：

```
main ────────────────────────────────────►  (永远可发布)
  │
  ├── feat/folder-tree   ──► PR ──► review ──► merge
  ├── fix/pdf-fonts      ──► PR ──► review ──► merge
  └── chore/ci-setup     ──► PR ──► review ──► merge
```

**规则**：

- `main` 永远可发布，受保护，禁止直接 push
- 所有工作在功能分支进行，**通过 PR 合并**
- 分支生命周期短（≤ 5 天为佳）
- 长期分支只能是 `main`（无 `develop`、`release/*`）

### 1.1 分支命名

| 前缀 | 用途 | 例 |
|------|------|----|
| `feat/` | 新功能 | `feat/folder-tree` |
| `fix/` | bug 修复 | `fix/version-log-missing` |
| `refactor/` | 重构（不改行为）| `refactor/extract-pdf-service` |
| `chore/` | 杂项（依赖 / CI / 配置）| `chore/upgrade-fastapi` |
| `docs/` | 文档 | `docs/api-error-codes` |
| `test/` | 仅加测试 | `test/folder-service-edge` |

格式：`<prefix>/<kebab-case-summary>`，summary ≤ 5 词，**禁止**包含 ticket 号（写在 PR 描述里）。

## 2. Commit 规范（Conventional Commits）

格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 2.1 type

| type | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | bug 修复 |
| `refactor` | 重构 |
| `docs` | 文档 |
| `test` | 测试 |
| `chore` | 杂项 |
| `perf` | 性能 |
| `style` | 格式化（无逻辑变更）|
| `build` | 构建系统 / 依赖 |
| `ci` | CI 配置 |

### 2.2 scope

通常为模块名：`folder` / `procedure` / `parser` / `pdf` / `auth` / `db` / `api` / `ui`。

### 2.3 subject

- 现在时祈使句，**首字母小写**，**不加句号**
- ≤ 50 字符
- 中文也允许，但保持简洁

### 2.4 body

- 解释 **why**（不是 what，diff 自己会说话）
- 每行 ≤ 72 字符
- 可选

### 2.5 footer

- 关联 issue / PR：`Closes #123`、`Refs #456`
- 破坏性变更：以 `BREAKING CHANGE:` 开头

### 2.6 示例

```
feat(folder): support max-depth 5 with cycle detection

文件夹移动时增加循环引用检测；超过 5 层嵌套时抛 FOLDER_DEPTH_EXCEEDED。
该变更影响 folder_service.move() 与 PUT /folders/{id}。

Closes #42
```

```
fix(pdf): correct page number on cover

封面页错误地参与了 footer 总页数计算，导致首页显示「第1页/共T+1页」。
```

## 3. PR 流程

### 3.1 创建 PR

- 从最新 `main` 拉分支
- 推送后立即创建 **Draft PR**（让 CI 跑起来）
- PR 标题遵循 commit subject 规范
- 用 PR 模板填写：背景、变更、测试方式、关联 issue

### 3.2 PR 模板（`.github/pull_request_template.md`）

```markdown
## 背景 / Why
<!-- 这次改动要解决什么问题？无 issue 也要说一句。 -->

## 变更 / What
<!-- 改了什么。条目化，便于审阅。 -->
- 

## 测试 / How tested
<!-- 单测 / 集成测试 / 手测步骤 -->

## 影响范围 / Impact
<!-- 接口、DB 字段、配置等是否变更 -->

## 关联
<!-- Closes #123 -->
```

### 3.3 评审规则

- **至少 1 名** reviewer 批准（人员少时 self-review 也要走一遍）
- 涉及数据库迁移 / API 破坏性变更 / 安全敏感代码：**强制 2 名**
- reviewer 在 24h 内首次响应
- 评审重点：正确性 > 可读性 > 性能 > 风格（风格由 linter 保证）

### 3.4 合并方式

- 默认 **Squash merge**（保持 main 整洁，1 PR = 1 commit）
- 合并 commit 信息 = PR 标题 + PR 描述（body）
- merge 后立即删除远程分支

### 3.5 禁止

- 禁止 `git push --force` 到 `main`
- 禁止合并失败 CI 的 PR（除非显式标注 known issue）
- 禁止跳过代码评审（除非紧急 hotfix，事后补评审）

## 4. CI 关卡

每个 PR 必须通过：

| 检查 | 工具 | 阻塞 |
|------|------|------|
| Lint（后端）| `ruff check` | ✅ |
| Format（后端）| `ruff format --check` | ✅ |
| 类型检查（后端）| `mypy` | ✅ |
| 单测（后端）| `pytest`（覆盖率 ≥ 80%）| ✅ |
| Lint（前端）| `eslint` | ✅ |
| 类型检查（前端）| `vue-tsc` | ✅ |
| 单测（前端）| `vitest` | ✅ |
| 构建（前端）| `vite build` | ✅ |
| 迁移检查 | `alembic check` | ✅ |

## 5. Hotfix 流程

紧急生产 bug：

1. 从 `main` 拉 `hotfix/xxx` 分支
2. 修改 + 测试 + PR（标题加 `[HOTFIX]`）
3. 至少 1 名 reviewer，可异步评审
4. Squash merge → 立即部署
5. 事后补完整 review 与文档

## 6. Tag 与发版

- 用语义化版本：`v<major>.<minor>.<patch>`
- 发版时打 annotated tag：`git tag -a v0.1.0 -m "Release 0.1.0"`
- Tag 描述对应 `CHANGELOG.md` 中该版本的内容

## 7. 提交频率与粒度

- **常 commit、勤 push**：避免长时间本地分支
- 单 commit 聚焦单一目的（便于 revert）
- WIP commit 在 squash 后消失，不留痕

## 8. 钩子

`pre-commit` 强制在本地：

- `ruff format && ruff check --fix`
- `eslint --fix`
- 阻止提交 `.env`、`*.key`、`*.pem`、大于 5MB 的二进制（字体除外）

配置示例见 `.pre-commit-config.yaml`（Phase 0 末提供）。

## 9. 历史保护

- main 历史只能前进，**禁止** rebase / amend 已合并的 commit
- 仅在功能分支内可 rebase / amend
