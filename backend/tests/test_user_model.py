import pytest
from sqlalchemy.exc import IntegrityError

from app.models.company import Company
from app.models.user import User, UserStatus


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def test_user_defaults(db):
    c = _company(db, "acme")
    u = User(company_id=c.id, email="a@acme.com", password_hash="x", name="Alice")
    db.add(u)
    db.commit()
    db.refresh(u)
    assert u.status == UserStatus.active
    assert u.is_platform_admin is False
    assert u.locale == "zh-CN"


def test_email_unique_per_company(db):
    c = _company(db, "acme")
    db.add(User(company_id=c.id, email="dup@acme.com", password_hash="x", name="A"))
    db.commit()
    db.add(User(company_id=c.id, email="dup@acme.com", password_hash="y", name="B"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_same_email_across_companies(db):
    c1 = _company(db, "acme")
    c2 = _company(db, "globex")
    db.add(User(company_id=c1.id, email="same@x.com", password_hash="x", name="A"))
    db.add(User(company_id=c2.id, email="same@x.com", password_hash="y", name="B"))
    db.commit()  # no error
