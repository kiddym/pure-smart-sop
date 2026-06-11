import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppTopBar from '@/components/AppTopBar.vue'
import i18n from '@/i18n'
import { useThemeStore } from '@/store/theme'

// 最小路由 stub：只要 push 不报错即可
function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/procedures/folders', component: { template: '<div/>' } },
      { path: '/admin/config/organization', component: { template: '<div/>' } },
      { path: '/admin/config/sop', component: { template: '<div/>' } },
      { path: '/', component: { template: '<div/>' } },
    ],
  })
}

function mountTopBar(props: Record<string, unknown> = {}) {
  return mount(AppTopBar, {
    props: { collapsed: false, ...props },
    global: { plugins: [makeRouter(), i18n] },
  })
}

describe('AppTopBar', () => {
  // 内嵌的 UserMenu 调用 useAuthStore()，需要活跃的 pinia。
  beforeEach(() => setActivePinia(createPinia()))

  it('渲染品牌文字（i18n app.name）', () => {
    const w = mountTopBar()
    expect(w.text()).toContain('Smart SOP')
  })

  it('collapsed=false 折叠按钮 aria-label 为「折叠侧栏」', () => {
    const w = mountTopBar({ collapsed: false })
    expect(w.find('.topbar-toggle').attributes('aria-label')).toBe('折叠侧栏')
  })

  it('collapsed=true 折叠按钮 aria-label 为「展开侧栏」', () => {
    const w = mountTopBar({ collapsed: true })
    expect(w.find('.topbar-toggle').attributes('aria-label')).toBe('展开侧栏')
  })

  it('点击折叠按钮 emit toggle-sidebar', async () => {
    const w = mountTopBar()
    await w.find('.topbar-toggle').trigger('click')
    expect(w.emitted('toggle-sidebar')).toHaveLength(1)
  })

  it('不在顶栏渲染禁用的占位搜索框（全库搜索未上线前不占位）', () => {
    const w = mountTopBar()
    expect(w.find('input.topbar-search').exists()).toBe(false)
  })

  it('渲染主题切换按钮，点击切换暗/浅', async () => {
    const w = mountTopBar()
    const btn = w.find('.topbar-theme')
    expect(btn.exists()).toBe(true)
    const theme = useThemeStore()
    const before = theme.isDark
    await btn.trigger('click')
    expect(theme.isDark).toBe(!before)
  })

  it('不再渲染 ⚙ 设置下拉（配置入口已统一收归左侧栏）', () => {
    const w = mountTopBar()
    expect(w.find('.topbar-cog').exists()).toBe(false)
  })
})
