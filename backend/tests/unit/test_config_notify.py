from app.config import settings


def test_notify_due_soon_days_default():
    assert settings.notify_due_soon_days == 3


def test_notify_due_soon_days_is_int():
    assert isinstance(settings.notify_due_soon_days, int)
