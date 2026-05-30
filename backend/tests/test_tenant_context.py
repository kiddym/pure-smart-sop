from app import tenant


def test_default_is_none():
    assert tenant.get_current_company_id() is None
    assert tenant.is_bypassed() is False


def test_set_and_reset():
    token = tenant.set_current_company_id("c-1")
    assert tenant.get_current_company_id() == "c-1"
    tenant.reset_current_company_id(token)
    assert tenant.get_current_company_id() is None


def test_bypass_context_manager():
    tenant.set_current_company_id("c-1")
    with tenant.bypass_tenant_scope():
        assert tenant.is_bypassed() is True
    assert tenant.is_bypassed() is False
    assert tenant.get_current_company_id() == "c-1"
    tenant.set_current_company_id(None)
