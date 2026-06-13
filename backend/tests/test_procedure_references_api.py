"""SOP 参考关系 REST API。注册一家公司→在该租户下建源/目标草稿程序→打 references API。"""
from __future__ import annotations

import uuid

import pytest

from app import tenant
from app.models.procedure import Procedure
from app.models.user import User


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_proc(db, code: str) -> Procedure:
    proc = Procedure(
        procedure_group_id=str(uuid.uuid4()), folder_id=str(uuid.uuid4()),
        code=code, name=code, level_of_use="reference", version=1,
        status="DRAFT", is_current=True,
    )
    db.add(proc)
    db.flush()
    return proc


@pytest.fixture
def authed_pair(client, db):
    token = client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@acme.com", "password": "secret123", "name": "Admin"},
    ).json()["access_token"]
    with tenant.bypass_tenant_scope():
        company_id = db.query(User).filter_by(email="a@acme.com").first().company_id

    ctx = tenant.set_current_company_id(company_id)
    try:
        src = _make_proc(db, "QC-00001")
        tgt = _make_proc(db, "QC-00002")
        db.commit()
        ids = {
            "source_id": src.id,
            "source_group": src.procedure_group_id,
            "target_group": tgt.procedure_group_id,
            "target_id": tgt.id,
        }
    finally:
        tenant.reset_current_company_id(ctx)
    return {"token": token, **ids}


def test_crud_flow(client, authed_pair):
    h = _h(authed_pair["token"])
    sid = authed_pair["source_id"]
    # create
    r = client.post(f"/api/v1/procedures/{sid}/references", headers=h, json={
        "target_procedure_group_id": authed_pair["target_group"],
        "relation_type": "exec_ref",
        "note": "先隔离上游",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    rid = body["id"]
    assert body["target_code"] == "QC-00002"        # 目标当前版本快照已解析
    assert body["target_procedure_id"] == authed_pair["target_id"]
    # list
    r = client.get(f"/api/v1/procedures/{sid}/references", headers=h)
    assert r.status_code == 200
    assert [x["id"] for x in r.json()] == [rid]
    # patch
    r = client.patch(f"/api/v1/references/{rid}", headers=h, json={"note": "改：先确认阀位"})
    assert r.status_code == 200, r.text
    assert r.json()["note"] == "改：先确认阀位"
    # delete
    r = client.delete(f"/api/v1/references/{rid}", headers=h)
    assert r.status_code == 204
    assert client.get(f"/api/v1/procedures/{sid}/references", headers=h).json() == []


def test_create_self_reference_returns_422(client, authed_pair):
    h = _h(authed_pair["token"])
    r = client.post(f"/api/v1/procedures/{authed_pair['source_id']}/references", headers=h, json={
        "target_procedure_group_id": authed_pair["source_group"],  # 目标=源自身 group
        "relation_type": "upstream",
    })
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "REFERENCE_SELF"
