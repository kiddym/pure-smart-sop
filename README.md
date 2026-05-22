# Smart SOP

独立的结构化 SOP（标准作业程序）管理系统。从 DPMS V2.0 的 procedure 模块剥离而来，**不含**用户、角色、审批工作流等耦合，可独立部署使用。

## 核心能力

- SOP 程序的 CRUD（含程序库、草稿管理、批量操作）
- 结构化编辑（章节 + 步骤的树形组织，富文本内容）
- Word 文档（.docx）→ 结构化 SOP 智能转换（标准 + 智能两种解析模式）
- 程序版本控制（整数版本号 + JSON 变更日志）
- 文件夹体系（树形最大 5 层、前缀编码、序列号自动重置）
- PDF 预览与下载（ReportLab 绘制，含封面/目录/修订页）
- 程序自定义字段（系统级扩展字段）
- 程序废止 / 恢复
- 全量审计日志（IP / UA / 时间）

## 技术栈

| 层 | 选型 |
|----|------|
| 前端 | Vue 3 + Element Plus + Pinia + Vue Router + Vite + TypeScript + Tailwind |
| 后端 | FastAPI（同步）+ SQLAlchemy 2.0 + Pydantic v2 + Alembic |
| 数据库 | MySQL 8.0 |
| Word 解析 | python-docx |
| PDF 生成 | ReportLab |

## 目录结构

```
smart-sop/
├── backend/        # FastAPI 后端
├── frontend/       # Vue 3 前端
├── docs/           # 项目文档（规范、计划、设计）
├── scripts/        # 运维 / 开发辅助脚本
├── .github/        # CI/CD 配置
└── docker-compose.yml
```

详细子目录见 [docs/data-model.md](docs/data-model.md) 与各组件 README。

## 快速开始

> 完整步骤见 [docs/deployment.md](docs/deployment.md)。

### 后端

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # 按需修改数据库配置
alembic upgrade head
uvicorn app.main:app --reload
```

后端启动后访问 <http://localhost:8000/docs> 查看 OpenAPI。

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认监听 <http://localhost:5173>，通过 Vite 代理转发到后端。

### 一键 Docker 起服务

```bash
docker-compose up -d
```

## 文档导航

完整文档索引见 [docs/README.md](docs/README.md)。常用入口：

- 项目设计与计划：[development-plan.md](docs/development-plan.md)
- 数据模型：[data-model.md](docs/data-model.md)
- API 规范：[api-specification.md](docs/api-specification.md)
- 后端规范：[backend-coding-standards.md](docs/backend-coding-standards.md)
- 前端规范：[frontend-coding-standards.md](docs/frontend-coding-standards.md)
- 数据库规范：[database-specification.md](docs/database-specification.md)
- Git 工作流：[git-workflow.md](docs/git-workflow.md)
- 测试规范：[testing-standards.md](docs/testing-standards.md)
- 部署文档：[deployment.md](docs/deployment.md)

## 项目状态

当前为初始化阶段（Phase 0）。开发进度详见 [development-plan.md](docs/development-plan.md)。
