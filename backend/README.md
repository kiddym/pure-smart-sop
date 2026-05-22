# Smart SOP Backend

FastAPI 同步 + SQLAlchemy 2.0 + MySQL 8.0。

## 目录结构

```
backend/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置（Pydantic Settings）
│   ├── db.py                # SQLAlchemy engine + SessionLocal
│   ├── deps.py              # 依赖注入
│   ├── middleware.py        # 审计中间件
│   ├── seed.py              # 启动种子数据
│   ├── models/              # ORM 模型
│   ├── schemas/             # Pydantic 模型
│   ├── routers/             # HTTP 路由
│   ├── services/            # 业务逻辑
│   │   └── pdf/             # PDF 生成
│   ├── parser/              # Word 文档解析
│   └── assets/fonts/        # 中文字体（PDF）
├── alembic/                 # 数据库迁移
├── tests/
│   ├── unit/
│   └── integration/
├── alembic.ini
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
└── .env.example
```

> 大多数子目录目前只有 `__init__.py`，Phase 1 起开始填充。

## 开发指引

详见根目录 [`docs/deployment.md`](../docs/deployment.md) 与 [`docs/backend-coding-standards.md`](../docs/backend-coding-standards.md)。
