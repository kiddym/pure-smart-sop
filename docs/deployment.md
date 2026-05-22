# 部署文档（Deployment）

> 本文件描述 Smart SOP 在三种环境下的部署方式：本地开发、Docker 一键起服、生产环境。

## 1. 环境要求

| 项 | 最低版本 |
|---|--------|
| Python | 3.11 |
| Node.js | 20.x LTS |
| MySQL | 8.0 |
| Docker | 24.x（可选） |
| Docker Compose | v2 |

## 2. 环境变量

所有可配置项通过 `.env` 文件（开发期）或环境变量（生产期）注入。后端读取见 [`backend/.env.example`](../backend/.env.example)。

| 变量 | 默认 | 说明 |
|------|------|------|
| `APP_ENV` | `development` | development / production |
| `APP_HOST` | `0.0.0.0` | uvicorn 监听地址 |
| `APP_PORT` | `8000` | uvicorn 监听端口 |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `DATABASE_URL` | `mysql+pymysql://root:root@localhost:3306/smart_sop` | SQLAlchemy 连接串 |
| `DATABASE_POOL_SIZE` | `10` | 连接池基础大小 |
| `DATABASE_MAX_OVERFLOW` | `20` | 连接池溢出上限 |
| `CORS_ORIGINS` | `http://localhost:5173` | 逗号分隔的允许来源 |
| `TRUSTED_PROXIES` | `127.0.0.1` | 可信反代 IP（逗号分隔）；审计中间件据此解析 `X-Forwarded-For` 取真实客户端 IP（Q324）|
| `UPLOAD_MAX_SIZE_MB` | `50` | Word 上传单文件上限 |
| `CLEANUP_HOUR` | `3` | scheduler 每日清理时刻（服务器时区 0–23，Q332）|
| `PDF_FONT_DIR` | `app/assets/fonts` | 字体目录（内置 SimSun / SimHei）|

前端用 Vite 环境变量：

| 变量 | 默认 | 说明 |
|------|------|------|
| `VITE_API_BASE_URL` | `/api/v1` | 后端 API 前缀（生产由 nginx 反向代理）|

## 3. 本地开发

### 3.1 启动 MySQL

任选一种：

**A. Docker（推荐）**：

```bash
docker run -d --name smart-sop-mysql \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=smart_sop \
  -p 3306:3306 \
  mysql:8.0
```

**B. 本机 MySQL**：

```sql
CREATE DATABASE smart_sop CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

### 3.2 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                    # 按需修改
alembic upgrade head                    # 跑迁移
python -m app.seed                      # 预置「废止」文件夹 + Settings
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 <http://localhost:8000/docs> 查看 Swagger UI。

### 3.3 启动前端

```bash
cd frontend
npm install
cp .env.example .env.development        # 按需修改 VITE_API_BASE_URL
npm run dev
```

访问 <http://localhost:5173>。Vite 已配置代理 `/api/v1 → http://localhost:8000`。

### 3.4 常用脚本

| 命令 | 用途 |
|------|------|
| `cd backend && pytest` | 后端测试 |
| `cd backend && ruff format && ruff check --fix` | 后端格式化 + lint |
| `cd backend && mypy app` | 后端类型检查 |
| `cd backend && alembic revision --autogenerate -m "<slug>"` | 生成迁移 |
| `cd frontend && npm run lint` | 前端 lint |
| `cd frontend && npm run typecheck` | 前端类型检查 |
| `cd frontend && npm run test` | 前端测试 |
| `cd frontend && npm run build` | 前端生产构建 |

## 4. Docker 一键起服

仓库根目录提供 `docker-compose.yml`，包含 3 个服务：

- `mysql`：MySQL 8.0
- `backend`：FastAPI（gunicorn + uvicorn worker）
- `frontend`：nginx 静态托管 + 反向代理 `/api`

```bash
# 首次构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f backend

# 进入后端容器跑迁移（自动跑，可手工触发）
docker-compose exec backend alembic upgrade head

# 停止
docker-compose down

# 完全清空（含数据卷）
docker-compose down -v
```

访问 <http://localhost> 进入前端。

### 4.1 镜像构建

后端 Dockerfile（`backend/Dockerfile`）：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m compileall app
EXPOSE 8000
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

前端 Dockerfile（`frontend/Dockerfile`）：多阶段构建，第一阶段 `npm run build`，第二阶段 nginx 托管 `dist/`。

## 5. 生产部署

> **⚠ 安全前提（硬性，Q322）**：Smart SOP **全接口匿名、可写**，App 层**无任何鉴权**。这只在**受信任内网 / LAN** 部署才成立——**严禁直接暴露公网**。任何能访问到 API 的人都能读写 / 删除 / 废止任意程序（破坏性操作靠软删 + restore + 审计兜底，Q325）。
>
> 若**必须**经公网访问，部署方**自行**在网络层加门禁（任选）：① VPN / 零信任网关；② nginx `auth_basic`（HTTP Basic-Auth）；③ nginx `allow/deny` IP allowlist。门禁**不进 App**，由反代承担。

### 5.1 部署架构

```
        ┌──────────────────────────────┐
        │     Reverse Proxy (nginx)    │
        │  - TLS 终止                  │
        │  - 限流                      │
        └────────┬─────────────────────┘
                 │
         ┌───────┴────────┐
         │                │
  ┌──────▼─────┐   ┌──────▼──────┐
  │  frontend  │   │   backend   │
  │  (nginx)   │   │  (gunicorn) │
  └────────────┘   └──────┬──────┘
                          │
                   ┌──────▼──────┐
                   │   MySQL     │
                   └─────────────┘
```

> 另有独立 `scheduler` 服务（APScheduler，**replicas=1**，Q331/§53）连 MySQL 跑周期清理（附件 / asset GC / 临时上传），不进请求链路、不可扩容。

### 5.2 部署清单

- [ ] 准备域名 + TLS 证书
- [ ] MySQL 用独立实例（不与应用同机），开启 binlog
- [ ] **确认部署于受信任内网 / LAN（Q322 硬前提）；如须公网，先在反代加门禁（VPN / Basic-Auth / IP allowlist）**
- [ ] 配置 `.env`（关键：`APP_ENV=production`、`LOG_LEVEL=INFO`、`DATABASE_URL`、`CORS_ORIGINS`、`TRUSTED_PROXIES`）
- [ ] 内置中文字体到镜像（`app/assets/fonts/`）
- [ ] 反向代理配置（见 5.3，含 X-Forwarded-For 透传 + 限流分桶）
- [ ] 启动前跑 `alembic upgrade head`
- [ ] 启动前跑 `python -m app.seed`
- [ ] 启动 `scheduler` 服务（独立进程，replicas=1，勿扩容，Q331）
- [ ] 健康检查接口 `GET /healthz` 配置到负载均衡

### 5.3 nginx 配置示例

```nginx
upstream backend {
    server backend:8000;
}

# 限流分桶（Q323）。写桶仅 POST/PUT/DELETE 计入（读请求 key 为空 → 不计），读桶覆盖全部。
map $request_method $write_key {
    default "";
    POST    $binary_remote_addr;
    PUT     $binary_remote_addr;
    PATCH   $binary_remote_addr;
    DELETE  $binary_remote_addr;
}
limit_req_zone $write_key          zone=api_write:10m rate=60r/m;
limit_req_zone $binary_remote_addr zone=api_read:10m  rate=300r/m;
limit_req_zone $binary_remote_addr zone=uploads:10m   rate=10r/m;
limit_req_zone $binary_remote_addr zone=parse:10m     rate=10r/m;
limit_req_zone $binary_remote_addr zone=pdf:10m       rate=20r/m;

server {
    listen 443 ssl http2;
    server_name smart-sop.example.com;

    ssl_certificate /etc/letsencrypt/live/.../fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/.../privkey.pem;

    client_max_body_size 60m;

    # 受控内网前提（Q322）；若须公网访问，在此 location 加 auth_basic 或 allow/deny。
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 60s;

        # 读 300/min（全部）+ 写 60/min（仅 POST/PUT/DELETE）
        limit_req zone=api_read  burst=50 nodelay;
        limit_req zone=api_write burst=10 nodelay;

        # 关键接口更严（子 location 自带 limit_req，不继承上面的通用桶）
        location = /api/v1/uploads {
            limit_req zone=uploads burst=3 nodelay;
            proxy_pass http://backend;
        }
        location = /api/v1/parse {
            limit_req zone=parse burst=5 nodelay;
            proxy_pass http://backend;
        }
        location ~ /pdf- {
            limit_req zone=pdf burst=5 nodelay;
            proxy_pass http://backend;
        }
    }

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
}
```

### 5.4 健康检查

后端必须实现：

- `GET /healthz` → 200 OK（仅检查应用存活，不查 DB）
- `GET /readyz` → 200 OK（检查 DB 连通）

部署到 k8s 时分别用作 liveness / readiness probe。

## 6. 备份与恢复

### 6.1 备份策略

| 类型 | 频率 | 保留 |
|------|------|-----|
| 全量 mysqldump | 每日 02:00 | 30 天 |
| binlog | 持续 | 7 天 |
| 关键变更前 | 手工触发 | 永久（归档存储） |

备份脚本示例（`scripts/backup.sh`）：

```bash
#!/usr/bin/env bash
set -euo pipefail
DATE=$(date +%Y%m%d_%H%M%S)
mysqldump -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" \
  --single-transaction --routines --triggers \
  smart_sop | gzip > /backup/smart_sop_$DATE.sql.gz
find /backup -name "smart_sop_*.sql.gz" -mtime +30 -delete
```

### 6.2 恢复演练

每季度 1 次：

1. 在隔离环境恢复最近一次备份
2. 跑 `alembic current` 确认 schema 版本
3. 跑 e2e 测试套件
4. 记录恢复时长（RTO）

## 7. 监控与日志

### 7.1 日志

- 应用日志输出到 stdout，由容器编排系统收集
- 格式：JSON（生产）/ 人类可读（开发）
- 字段：`time`、`level`、`logger`、`message`、`request_id`（如有）

### 7.2 监控指标

> 由**基础设施侧**采集（反代访问日志 + 容器 / 编排平台），**不内嵌 APM / 应用指标后端 / 链路追踪**（Q329）。最小集：

- HTTP 响应码分布（2xx / 4xx / 5xx）
- p50 / p95 / p99 响应时长
- DB 连接池使用率
- 慢查询数量
- 磁盘使用率（PDF 缓存）

## 8. 升级流程

1. 在测试环境验证新版本（含数据迁移）
2. 生产环境 PR 合并后：
   - 备份数据库
   - 应用新版本镜像
   - 跑 `alembic upgrade head`
   - 重启 backend（滚动）
   - 烟雾测试关键流程
3. 若失败：回滚镜像 + `alembic downgrade <prev_revision>`

## 9. 安全检查清单

- [ ] **部署于受信任内网；公网暴露须经网络层门禁（Q322）**——App 无鉴权、全匿名可写
- [ ] `.env` 不进版本控制
- [ ] 数据库账号最小权限（不给 SUPER / FILE）
- [ ] 反向代理强制 HTTPS + 透传 `X-Forwarded-For`，后端配 `TRUSTED_PROXIES`（审计真实 IP，Q324）
- [ ] 限流分桶（uploads / parse / pdf-* / 写 / 读，Q323）
- [ ] 文件上传校验扩展名 + MIME + 大小
- [ ] 日志不含敏感数据
- [ ] 定期升级依赖（`pip list --outdated`、`npm outdated`）

## 10. 故障排查

| 现象 | 排查方向 |
|------|---------|
| 启动报 `Table doesn't exist` | 是否跑过 `alembic upgrade head` |
| 创建程序 `code` 为 `-0001` | folder.prefix 是否为空 |
| PDF 中文乱码 | 字体文件是否打包进镜像 / `PDF_FONT_DIR` 路径是否正确 |
| CORS 报错 | `CORS_ORIGINS` 是否包含前端域名 |
| 上传 .docx 超时 | nginx `client_max_body_size`、后端 `UPLOAD_MAX_SIZE_MB` |
