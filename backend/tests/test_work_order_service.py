import pytest
from fastapi import HTTPException

from app import tenant
from app.models.company import Company
from app.models.user import User
from app.models.work_order_status import WorkOrderStatus
from app.schemas.work_order import WorkOrderCreate, WorkOrderTransition, WorkOrderUpdate
from app.services import work_order_service as svc


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def _ctx(company_id):
    tenant.set_current_company_id(company_id)


def test_create_assigns_custom_id(db):
    c = _company(db, "acme")
    _ctx(c.id)
    a = svc.create_work_order(db, WorkOrderCreate(title="泵1"), c.id, actor_user_id=None)
    b = svc.create_work_order(db, WorkOrderCreate(title="泵2"), c.id, actor_user_id=None)
    assert a.custom_id == "WO000001"
    assert b.custom_id == "WO000002"
    assert a.status == WorkOrderStatus.OPEN


def test_tenants_independent_custom_id(db):
    c1 = _company(db, "acme"); c2 = _company(db, "globex")
    _ctx(c1.id)
    a = svc.create_work_order(db, WorkOrderCreate(title="x"), c1.id, actor_user_id=None)
    _ctx(c2.id)
    b = svc.create_work_order(db, WorkOrderCreate(title="y"), c2.id, actor_user_id=None)
    assert a.custom_id == "WO000001" and b.custom_id == "WO000001"


def test_assignees_replace_and_dedupe(db):
    c = _company(db, "acme")
    _ctx(c.id)
    u1 = User(company_id=c.id, email="u1@a.com", password_hash="x", name="U1")
    u2 = User(company_id=c.id, email="u2@a.com", password_hash="x", name="U2")
    db.add_all([u1, u2]); db.commit()
    wo = svc.create_work_order(db, WorkOrderCreate(title="t"), c.id, actor_user_id=None)
    svc.set_assignees(db, wo, [u1.id, u2.id, u1.id], c.id)
    assert set(svc.assignee_ids(db, wo.id)) == {u1.id, u2.id}
    svc.set_assignees(db, wo, [u1.id], c.id)
    assert svc.assignee_ids(db, wo.id) == [u1.id]


def test_legal_transition_writes_activity(db):
    c = _company(db, "acme")
    _ctx(c.id)
    wo = svc.create_work_order(db, WorkOrderCreate(title="t"), c.id, actor_user_id="u9")
    svc.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS),
                   c.id, actor_user_id="u9")
    assert wo.status == WorkOrderStatus.IN_PROGRESS
    acts = svc.list_activities(db, wo.id)
    assert any(a.activity_type == "STATUS_CHANGE" and a.to_status == "IN_PROGRESS" for a in acts)


def test_illegal_transition_rejected(db):
    c = _company(db, "acme")
    _ctx(c.id)
    wo = svc.create_work_order(db, WorkOrderCreate(title="t"), c.id, actor_user_id=None)
    with pytest.raises(HTTPException) as exc:
        svc.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.COMPLETE),
                       c.id, actor_user_id=None)
    assert exc.value.status_code == 400


def test_complete_sets_and_reopen_clears_completed_at(db):
    c = _company(db, "acme")
    _ctx(c.id)
    wo = svc.create_work_order(db, WorkOrderCreate(title="t"), c.id, actor_user_id=None)
    svc.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    svc.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.COMPLETE), c.id, None)
    assert wo.completed_at is not None
    svc.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    assert wo.completed_at is None


def test_update_and_soft_delete(db):
    c = _company(db, "acme")
    _ctx(c.id)
    wo = svc.create_work_order(db, WorkOrderCreate(title="t"), c.id, actor_user_id=None)
    svc.update_work_order(db, wo, WorkOrderUpdate(title="t2", description="d"))
    assert wo.title == "t2" and wo.description == "d"
    svc.delete_work_order(db, wo)
    assert wo.is_active is False
    assert svc.get_work_order(db, wo.id) is None


def test_comment_activity(db):
    c = _company(db, "acme")
    _ctx(c.id)
    wo = svc.create_work_order(db, WorkOrderCreate(title="t"), c.id, actor_user_id=None)
    svc.add_comment(db, wo, "需要备件", c.id, actor_user_id="u3")
    acts = svc.list_activities(db, wo.id)
    assert any(a.activity_type == "COMMENT" and a.comment == "需要备件" for a in acts)
