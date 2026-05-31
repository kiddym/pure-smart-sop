from app import permissions as perms


def test_analytics_view_registered():
    assert "analytics.view" in perms.ALL_PERMISSIONS


def test_no_duplicate_codes():
    assert len(perms.ALL_PERMISSIONS) == len(set(perms.ALL_PERMISSIONS))


def test_super_admin_and_admin_have_analytics():
    assert "analytics.view" in perms.effective_codes("super_admin", [])
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    assert "analytics.view" in admin["permissions"]


def test_viewer_includes_analytics_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "analytics.view" in viewer["permissions"]


def test_technician_excluded_from_analytics():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "analytics.view" not in tech["permissions"]


def test_requester_unchanged():
    requester = next(r for r in perms.BUILTIN_ROLES if r["code"] == "requester")
    assert set(requester["permissions"]) == {"request.view", "request.create"}
