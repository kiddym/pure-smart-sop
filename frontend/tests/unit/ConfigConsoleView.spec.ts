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

  it('系统设置指向组织设置页（无 tab 参数）', () => {
    const wrapper = mountHub()
    const targets = wrapper.findAllComponents(RouterLinkStub).map((l) => l.props('to'))
    expect(targets).toContain('/admin/config/organization')
  })
})
