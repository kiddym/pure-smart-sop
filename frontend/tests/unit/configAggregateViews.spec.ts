import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SopConfigView from '@/views/admin/config/SopConfigView.vue'

// stub all embedded children — aggregate pages only own the tab skeleton
const stubs = {
  FieldManageView: { template: '<div class="s-field-manage" />' },
  HeadingRulesView: { template: '<div class="s-heading-rules" />' },
}

function mountWith(comp: unknown, query: Record<string, string> = {}) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: comp as never }] })
  router.push({ path: '/', query })
  return router.isReady().then(() =>
    mount(comp as never, { global: { plugins: [createPinia(), router], stubs } }),
  )
}

describe('SopConfigView', () => {
  it('渲染程序字段与标题字典两个 tab', async () => {
    const w = await mountWith(SopConfigView)
    const labels = w.findAll('.el-tabs__item').map((n) => n.text())
    expect(labels).toEqual(expect.arrayContaining(['程序字段', '标题字典']))
  })
  it('按 query.tab=heading-rules 选中标题字典', async () => {
    const w = await mountWith(SopConfigView, { tab: 'heading-rules' })
    expect(w.find('.el-tabs__item.is-active').text()).toBe('标题字典')
  })
})
