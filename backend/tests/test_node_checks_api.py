"""核查点 REST API。注册一家公司→在该租户下建草稿程序+step 节点→打 checks API。

要点：API 请求期租户上下文来自 JWT（deps.get_current_user），故被测节点必须归属
注册用户的公司，否则 tenant 行级作用域会让它对 authed 请求不可见。
"""
from __future__ import annotations

import uuid

import pytest

from app import tenant
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.models.user import User


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authed_step(client, db):
    token = client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "Admin"},
    ).json()["access_token"]
    with tenant.bypass_tenant_scope():
        company_id = db.query(User).filter_by(email="a@acme.com").first().company_id

    ctx = tenant.set_current_company_id(company_id)
    try:
        proc = Procedure(
            procedure_group_id=str(uuid.uuid4()), folder_id=str(uuid.uuid4()),
            code="QC-00001", name="P", level_of_use="reference", version=1,
            status="DRAFT", is_current=True,
        )
        db.add(proc)
        db.flush()
        node = ProcedureNode(procedure_id=proc.id, body="读压力表", kind="step", sort_order=1000)
        db.add(node)
        db.commit()
        node_id = node.id
    finally:
        tenant.reset_current_company_id(ctx)
    return {"token": token, "node_id": node_id}


def test_crud_flow(client, authed_step):
    h = _h(authed_step["token"])
    nid = authed_step["node_id"]
    # create
    r = client.post(f"/api/v1/nodes/{nid}/checks", headers=h, json={
        "check_type": "safety", "params": {"items": ["gloves"]}, "prompt": "戴手套",
    })
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    # list
    r = client.get(f"/api/v1/nodes/{nid}/checks", headers=h)
    assert r.status_code == 200
    assert [c["id"] for c in r.json()] == [cid]
    # patch
    r = client.patch(f"/api/v1/checks/{cid}", headers=h, json={"prompt": "请戴丁腈手套"})
    assert r.status_code == 200, r.text
    assert r.json()["prompt"] == "请戴丁腈手套"
    # delete
    r = client.delete(f"/api/v1/checks/{cid}", headers=h)
    assert r.status_code == 204
    r = client.get(f"/api/v1/nodes/{nid}/checks", headers=h)
    assert r.json() == []


def test_create_invalid_returns_422(client, authed_step):
    r = client.post(
        f"/api/v1/nodes/{authed_step['node_id']}/checks",
        headers=_h(authed_step["token"]),
        json={"check_type": "ocr", "params": {}},
    )
    assert r.status_code == 422
