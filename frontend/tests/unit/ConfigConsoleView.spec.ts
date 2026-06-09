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

  it('渲染六个部署阶段区块', () => {
    const wrapper = mountHub()
    const text = wrapper.text()
    for (const t of ['组织基础', '人员权限', '全局参数', '业务模块', '自动化', '运维']) {
      expect(text).toContain(t)
    }
  })
  it('业务模块区块含四个聚合页入口', () => {
    const wrapper = mountHub()
    const targets = wrapper.findAllComponents(RouterLinkStub).map((l) => l.props('to'))
    for (const to of ['/admin/config/sop', '/admin/config/work-order', '/admin/config/request', '/admin/config/custom-fields']) {
      expect(targets).toContain(to)
    }
  })
  it('组织基础/全局参数指向组织设置聚合页对应 tab', () => {
    const wrapper = mountHub()
    const targets = wrapper.findAllComponents(RouterLinkStub).map((l) => l.props('to'))
    expect(targets).toContain('/admin/config/organization?tab=company')
    expect(targets).toContain('/admin/config/organization?tab=global')
  })
  it('货币入口仅 super_admin 可见', () => {
    setRole('super_admin')
    const adminTargets = mountHub()
      .findAllComponents(RouterLinkStub)
      .map((l) => l.props('to'))
    expect(adminTargets).toContain('/admin/currencies')

    setRole('manager')
    const mgrTargets = mountHub()
      .findAllComponents(RouterLinkStub)
      .map((l) => l.props('to'))
    expect(mgrTargets).not.toContain('/admin/currencies')
  })
})
