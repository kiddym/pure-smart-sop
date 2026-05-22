"""编辑器端点集成测试：章节 / 步骤 / 转换 / 标记 + 嵌套 GET（api-specification §5.4）。"""

from __future__ import annotations

from fastapi.testclient import TestClient

PROC = "/api/v1/procedures"
FOLDER = "/api/v1/folders"
CH = "/api/v1/chapters"
STEP = "/api/v1/steps"


def _proc(client: TestClient, *, prefix: str = "QC") -> str:
    fid = client.post(FOLDER, json={"name": "叶子", "prefix": prefix}).json()["id"]
    return client.post(
        PROC, json={"folder_id": fid, "name": "启动 SOP", "level_of_use": "continuous"}
    ).json()["id"]


def _chapter(client: TestClient, pid: str, **kw: object) -> dict:
    body = {"procedure_id": pid, "content_type": "chapter", "title": "章"}
    body.update(kw)
    resp = client.post(CH, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# 章节 CRUD + 编号
# --------------------------------------------------------------------------- #
def test_create_chapter_and_nested_get(client: TestClient) -> None:
    pid = _proc(client)
    l1 = _chapter(client, pid, title="概述")
    _chapter(client, pid, content_type="content", rich_content="<p>说明</p>", parent_id=l1["id"])
    detail = client.get(f"{PROC}/{pid}").json()
    assert len(detail["chapters"]) == 1
    root = detail["chapters"][0]
    assert root["code"] == "1"
    assert root["content_type"] == "chapter"
    assert len(root["children"]) == 1
    assert root["children"][0]["content_type"] == "content"
    assert root["children"][0]["rich_content"] == "<p>说明</p>"


def test_chapter_rich_content_rejected_400(client: TestClient) -> None:
    pid = _proc(client)
    resp = client.post(
        CH,
        json={
            "procedure_id": pid,
            "content_type": "chapter",
            "title": "x",
            "rich_content": "<p>y</p>",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "CHAPTER_RICH_CONTENT_NOT_ALLOWED"


def test_depth_exceeded_400(client: TestClient) -> None:
    pid = _proc(client)
    l1 = _chapter(client, pid)
    l2 = _chapter(client, pid, parent_id=l1["id"])
    l3 = _chapter(client, pid, parent_id=l2["id"])
    resp = client.post(
        CH,
        json={"procedure_id": pid, "content_type": "chapter", "title": "L4", "parent_id": l3["id"]},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "CHAPTER_DEPTH_EXCEEDED"


def test_move_up_reorders(client: TestClient) -> None:
    pid = _proc(client)
    a = _chapter(client, pid, title="A")
    b = _chapter(client, pid, title="B")
    resp = client.post(f"{CH}/{b['id']}/move-up")
    assert resp.status_code == 200
    detail = client.get(f"{PROC}/{pid}").json()
    titles = [c["title"] for c in detail["chapters"]]
    assert titles == ["B", "A"]
    assert detail["chapters"][0]["code"] == "1"
    _ = a


def test_delete_chapter_recursive(client: TestClient) -> None:
    pid = _proc(client)
    p = _chapter(client, pid, title="P")
    _chapter(client, pid, title="C", parent_id=p["id"])
    resp = client.delete(f"{CH}/{p['id']}")
    assert resp.status_code == 204
    detail = client.get(f"{PROC}/{pid}").json()
    assert detail["chapters"] == []


# --------------------------------------------------------------------------- #
# 步骤
# --------------------------------------------------------------------------- #
def test_create_step_and_flat_list(client: TestClient) -> None:
    pid = _proc(client)
    ch = _chapter(client, pid, title="操作")
    resp = client.post(STEP, json={"procedure_id": pid, "chapter_id": ch["id"], "title": "启动"})
    assert resp.status_code == 201, resp.text
    detail = client.get(f"{PROC}/{pid}").json()
    assert len(detail["steps"]) == 1
    assert detail["steps"][0]["code"] == "1.1"
    assert detail["steps"][0]["chapter_id"] == ch["id"]


def test_step_sibling_conflict_400(client: TestClient) -> None:
    pid = _proc(client)
    parent = _chapter(client, pid, title="父")
    _chapter(client, pid, title="子", parent_id=parent["id"])
    resp = client.post(STEP, json={"procedure_id": pid, "chapter_id": parent["id"]})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "SIBLING_TYPE_CONFLICT"


# --------------------------------------------------------------------------- #
# 转换
# --------------------------------------------------------------------------- #
def test_content_to_steps_http(client: TestClient) -> None:
    pid = _proc(client)
    parent = _chapter(client, pid, title="父")
    content = _chapter(
        client,
        pid,
        content_type="content",
        rich_content="<p>一</p><p>二</p>",
        parent_id=parent["id"],
    )
    resp = client.post(f"{CH}/{content['id']}/content-to-steps")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["created"]) == 2
    detail = client.get(f"{PROC}/{pid}").json()
    assert [s["code"] for s in detail["steps"]] == ["1.1", "1.2"]


def test_convert_to_content_returns_410(client: TestClient) -> None:
    pid = _proc(client)
    ch = _chapter(client, pid)
    resp = client.post(f"{CH}/{ch['id']}/convert-to-content")
    assert resp.status_code == 410
    assert resp.json()["detail"]["code"] == "CONVERT_TO_CONTENT_DEPRECATED"


def test_step_convert_to_chapter_http(client: TestClient) -> None:
    pid = _proc(client)
    parent = _chapter(client, pid, title="父")
    step = client.post(
        STEP,
        json={
            "procedure_id": pid,
            "chapter_id": parent["id"],
            "title": "步骤",
            "content": "<p>正文</p>",
        },
    ).json()
    resp = client.post(f"{STEP}/{step['id']}/convert-to-chapter")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["created"]) == 2


# --------------------------------------------------------------------------- #
# 标记模式
# --------------------------------------------------------------------------- #
def test_apply_marks_http(client: TestClient) -> None:
    pid = _proc(client)
    parent = _chapter(client, pid, title="父")
    x1 = _chapter(
        client, pid, content_type="content", rich_content="<p>a</p>", parent_id=parent["id"]
    )
    x2 = _chapter(
        client, pid, content_type="content", rich_content="<p>b</p>", parent_id=parent["id"]
    )
    assert (
        client.post(f"{CH}/{x1['id']}/mark-status", json={"mark_status": "step"}).status_code == 200
    )
    assert (
        client.post(f"{CH}/{x2['id']}/mark-status", json={"mark_status": "step"}).status_code == 200
    )
    resp = client.post(f"{PROC}/{pid}/apply-marks")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["created"]) == 2
    detail = client.get(f"{PROC}/{pid}").json()
    assert len(detail["steps"]) == 2


def test_batch_save_creates_tree_and_returns_id_map(client: TestClient) -> None:
    pid = _proc(client)
    body = {
        "name": "启动 SOP",
        "level_of_use": "continuous",
        "chapters": [
            {"id": "t1", "content_type": "chapter", "title": "概述", "sort_order": 0},
            {
                "id": "t2",
                "parent_id": "t1",
                "content_type": "content",
                "rich_content": "<p>说明</p>",
                "sort_order": 0,
            },
        ],
        "steps": [],
    }
    resp = client.put(f"{PROC}/{pid}", json=body, headers={"If-Match": "0"})
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert out["revision"] == 1
    assert set(out["id_map"]) == {"t1", "t2"}
    detail = client.get(f"{PROC}/{pid}").json()
    assert detail["chapters"][0]["code"] == "1"
    assert detail["chapters"][0]["children"][0]["rich_content"] == "<p>说明</p>"


def test_apply_marks_conflict_400(client: TestClient) -> None:
    pid = _proc(client)
    parent = _chapter(client, pid, title="父")
    x1 = _chapter(
        client, pid, content_type="content", rich_content="<p>a</p>", parent_id=parent["id"]
    )
    _chapter(client, pid, content_type="content", rich_content="<p>b</p>", parent_id=parent["id"])
    client.post(f"{CH}/{x1['id']}/mark-status", json={"mark_status": "step"})
    resp = client.post(f"{PROC}/{pid}/apply-marks")
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "SIBLING_TYPE_CONFLICT"
