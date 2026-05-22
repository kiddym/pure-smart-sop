# 测试规范（Testing Standards）

> 适用于 Smart SOP 前后端所有测试代码。

## 1. 测试理念

| 原则 | 说明 |
|------|------|
| **快速反馈** | 单测毫秒级，集成测试秒级，整套 ≤ 5 min |
| **关注行为而非实现** | 测公共 API 输出，不测私有细节 |
| **可独立运行** | 任意测试可单独跑，不依赖运行顺序 |
| **证据先于断言** | 看到运行通过再相信，不靠"看起来对" |
| **失败时信息充足** | 断言必须有上下文，便于定位 |

## 2. 测试金字塔

```
        e2e (Playwright)        ~10 个，覆盖关键用户流
       ─────────────────
      integration (httpx)       ~50 个，每个 API 至少 1 正例 1 反例
     ──────────────────────
    unit (pytest / vitest)      数百个，覆盖 service / 组件
   ──────────────────────────
```

**比例约束**：单测 70% + 集成 25% + e2e 5%。

## 3. 后端测试

### 3.1 目录结构

```
backend/tests/
├── conftest.py                   # 顶层 fixtures（db、client）
├── unit/                         # 单元测试，按模块对应
│   ├── services/
│   │   ├── test_folder_service.py
│   │   ├── test_procedure_service.py
│   │   └── test_sequence_generator.py
│   ├── parser/
│   └── pdf/
└── integration/                  # 接口集成测试
    ├── test_folders_api.py
    ├── test_procedures_api.py
    └── test_parse_api.py
```

### 3.2 命名

- 文件：`test_<module>.py`
- 函数：`test_<unit>_<behavior>`，如 `test_create_folder_with_duplicate_name_raises_409`
- 用 docstring 描述测试意图

### 3.3 Fixture

- 顶层 `conftest.py` 提供：
  - `db`：测试数据库 session（每个 test 自动 rollback）
  - `client`：FastAPI TestClient
  - `factory`：业务对象工厂（用 `factory-boy` 或手写）
- 模块级 fixture 放对应目录的 `conftest.py`

### 3.4 数据库

- 单测优先 SQLite in-memory（极快，CI 友好）
- 涉及 MySQL 特定行为（JSON、generated column）的测试用 MySQL test schema
- 每个 test function 用 transaction rollback 隔离

### 3.5 示例

```python
# tests/unit/services/test_folder_service.py
import pytest
from app.services import folder_service
from app.schemas.folder import FolderCreate


def test_create_folder_with_duplicate_name_raises(db, factory):
    """同一父目录下创建同名文件夹应该抛 409。"""
    parent = factory.folder(name="质检")
    folder_service.create(db, FolderCreate(name="检验", parent_id=parent.id))

    with pytest.raises(HTTPException) as exc:
        folder_service.create(db, FolderCreate(name="检验", parent_id=parent.id))

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "FOLDER_NAME_DUPLICATE"
```

### 3.6 集成测试

```python
# tests/integration/test_folders_api.py
def test_post_folder_returns_201_with_full_path(client):
    response = client.post("/api/v1/folders", json={"name": "质检", "prefix": "QC"})

    assert response.status_code == 201
    body = response.json()
    assert body["full_path"] == "质检"
    assert body["prefix"] == "QC"
```

### 3.7 覆盖率

- **目标**：service / parser / pdf 层 ≥ 80% 行覆盖
- router 层不强制（行为已被 integration 覆盖）
- 用 `pytest --cov=app --cov-report=term-missing --cov-fail-under=80`
- CI 上传 coverage report

## 4. 前端测试

### 4.1 目录结构

```
frontend/
├── src/
└── tests/
    ├── unit/
    │   ├── components/
    │   └── store/
    └── e2e/
        └── procedure-crud.spec.ts
```

### 4.2 单元 / 组件测试

- 工具：Vitest + `@vue/test-utils`
- 关注点：
  - props 渲染正确
  - emit 时机正确
  - 用户交互（click / input）触发预期行为
  - computed 输出正确
- API 调用用 **MSW** mock（Mock Service Worker），不直接 mock axios

### 4.3 示例

```typescript
// tests/unit/components/FolderTree.spec.ts
import { mount } from '@vue/test-utils'
import FolderTree from '@/components/FolderTree/FolderTree.vue'

test('点击节点触发 select 事件', async () => {
  const wrapper = mount(FolderTree, {
    props: { nodes: [{ id: '1', name: '质检', children: [] }] },
  })
  await wrapper.find('[data-testid="folder-node-1"]').trigger('click')
  expect(wrapper.emitted('select')).toEqual([['1']])
})
```

### 4.4 e2e

- 工具：Playwright
- 覆盖关键用户流：
  - 创建文件夹 → 创建程序 → 添加章节 → 保存
  - Word 上传 → 解析 → 审查 → 导入
  - 程序详情 → PDF 预览
  - 程序废止 → 在「废止」文件夹中可见 → 恢复

### 4.5 数据隔离

- e2e 测试每次跑前清空数据库 + 跑 seed
- 用 `beforeEach` 创建独立 fixture，不复用上一个 case 的副作用

## 5. 命名约定

| 类型 | 模式 |
|------|------|
| 单测函数 | `test_<unit>_<scenario>_<expected>` |
| 测试文件 | 与被测代码 1:1 对应 |
| 测试数据 | fixture 命名 `<entity>_<state>`，如 `folder_with_children` |

## 6. 必测场景清单（按模块）

### 6.1 sequence_generator

- 同 folder 并发 10 次生成，结果无重复
- 达到 `9999`（4 位）后下一个返回 `0001` 且记 WARN
- `reset_period=daily`，跨日后第一次生成归零
- `reset_period=never` 时永不归零

### 6.2 folder_service

- 嵌套 5 层成功；嵌套 6 层抛 `FOLDER_DEPTH_EXCEEDED`
- 移动 A 到 A 的子节点抛 `FOLDER_CYCLE_DETECTED`
- 删除有子文件夹的文件夹抛 `FOLDER_NOT_EMPTY`
- 删除有程序的文件夹抛 `FOLDER_NOT_EMPTY`
- 删除「系统」文件夹抛 `FOLDER_SYSTEM_PROTECTED`
- 重命名后 `full_path` 与所有子节点 `full_path` 同步更新

### 6.3 procedure_service

- 创建程序自动生成 code（前缀来自 folder.prefix）
- 状态机非法切换抛 `PROCEDURE_STATUS_INVALID`
- 非 `is_current=true AND status=DRAFT` 记录 PUT 抛 `PROCEDURE_READONLY`（ARCHIVED / 历史版本 / deprecated group 均覆盖）
- deprecate 后 folder_id 指向「废止」 + status=ARCHIVED + 写 audit_log
- restore 后回到原 folder_id（从 audit_log 取出）

### 6.4 version_service

- create 时 version_change_log 含 1 条 `create`
- update 时 version 不变（除非显式 upgrade）
- upgrade-version 后 version + 1，log 追加 `upgrade`
- 达到 `max_version_number` 后再 upgrade 抛 `PROCEDURE_VERSION_MAX`

### 6.5 parser

- 标准 .docx 解析返回 ≥ 1 个章节
- 非 .docx 文件抛 `PARSE_FILE_INVALID`
- 智能模式：含字号 + 加粗的伪标题被识别为 chapter
- 模板校验 H001-T002 各规则正反 case

### 6.6 pdf

- 单层程序 PDF 含封面 + 目录 + 内容页
- 多层章节（≥ 3 层）目录正确
- 长内容跨页时 footer 页码正确

## 7. CI 集成

`.github/workflows/test.yml`（占位）：

```yaml
name: test
on: [pull_request, push]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r backend/requirements-dev.txt
      - run: cd backend && pytest --cov=app --cov-fail-under=80
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd frontend && npm ci
      - run: cd frontend && npm run lint && npm run typecheck && npm run test
```

## 8. 反模式（不要这样做）

- ❌ 测试覆盖了所有行但不测行为（"覆盖率作弊"）
- ❌ 一个测试有多个 act + assert，失败时定位困难
- ❌ Test 之间共享可变状态
- ❌ Mock 到测试只是在测 mock 本身
- ❌ 删除失败的测试而不是修问题
