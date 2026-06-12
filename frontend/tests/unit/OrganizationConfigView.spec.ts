import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import OrganizationConfigView from '@/views/admin/config/OrganizationConfigView.vue'

// 公司设置已删除，本页直接渲染系统设置，无 tab 骨架，也不再依赖路由。
const stubs = {
  SettingsView: { template: '<div class="stub-global" />' },
}

function mountView() {
  return mount(OrganizationConfigView, {
    global: { plugins: [createPinia()], stubs },
  })
}

describe('OrganizationConfigView', () => {
  it('渲染页面标题「系统设置」', () => {
    const wrapper = mountView()
    expect(wrapper.find('.page-title').text()).toBe('系统设置')
  })

  it('直接渲染 SettingsView（无 tab）', () => {
    const wrapper = mountView()
    expect(wrapper.find('.stub-global').exists()).toBe(true)
    expect(wrapper.find('.el-tabs').exists()).toBe(false)
  })
})
