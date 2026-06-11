import { describe, it, expect, beforeEach } from 'vitest'
import { mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfigConsoleView from '@/views/admin/config/ConfigConsoleView.vue'
import { useAuthStore } from '@/store/auth'

function mountHub() {
  return mount(ConfigConsoleView, {
    global: { plugins: [], stubs: { 'router-link': RouterLinkStub } },
  })
}

function setRole(roleCode: string | null) {
  const auth = useAuthStore()
  auth.user = {
    id: 'u1',
    email: 'a@b.com',
    name: 'A',
    company_id: 'c1',
    role_code: roleCode,
    permissions: [],
  }
}

describe('ConfigConsoleView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    setRole('super_admin')
  })

  it('含 SOP 配置聚合页入口', () => {
    const wrapper = mountHub()
    const targets = wrapper.findAllComponents(RouterLinkStub).map((l) => l.props('to'))
    expect(targets).toContain('/admin/config/sop')
  })
  it('组织基础/全局参数指向组织设置聚合页对应 tab', () => {
    const wrapper = mountHub()
    const targets = wrapper.findAllComponents(RouterLinkStub).map((l) => l.props('to'))
    expect(targets).toContain('/admin/config/organization?tab=company')
    expect(targets).toContain('/admin/config/organization?tab=global')
  })
})
