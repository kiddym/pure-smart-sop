"""numbering-profiles REST CRUD（P1d）。"""
from __future__ import annotations


def test_crud_flow(client) -> None:
    r = client.post("/api/v1/numbering-profiles",
                    json={"pattern_key": "第X条", "kind": "heading", "level": 3})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    r = client.get("/api/v1/numbering-profiles")
    assert any(x["pattern_key"] == "第X条" for x in r.json())

    r = client.put(f"/api/v1/numbering-profiles/{pid}", json={"level": 2})
    assert r.status_code == 200 and r.json()["level"] == 2

    r = client.delete(f"/api/v1/numbering-profiles/{pid}")
    assert r.status_code == 204


def test_bad_kind_returns_409(client) -> None:
    r = client.post("/api/v1/numbering-profiles",
                    json={"pattern_key": "X", "kind": "bogus", "level": 1})
    assert r.status_code == 409, r.text
