import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'

function makeRouter(initialPath: string): Router {
  return createRouter({
    history: createMemoryHistory(initialPath),
    routes: [
      { path: '/procedures/library', component: { template: '<div/>' } },
      { path: '/procedures/drafts', component: { template: '<div/>' } },
      { path: '/procedures/:id', component: { template: '<div/>' } },
      { path: '/procedures/:id/edit', component: { template: '<div/>' } },
      { path: '/settings', component: { template: '<div/>' } },
      { path: '/', component: { template: '<div/>' } },
    ],
  })
}

async function mountSidebar(initialPath: string, collapsed = false) {
  const router = makeRouter(initialPath)
  await router.push(initialPath)
  await router.isReady()
  return mount(AppSidebar, {
    props: { collapsed },
    global: { plugins: [router] },
  })
}

describe('AppSidebar', () => {
  it('collapsed=false：1 个 group-label「内容」+ 2 个 menu-item', async () => {
    const w = await mountSidebar('/procedures/library')
    expect(w.findAll('.menu-group-label').length).toBe(1)
    expect(w.find('.menu-group-label').text()).toBe('内容')
    expect(w.findAll('.el-menu-item').length).toBe(2)
    expect(w.text()).toContain('程序库')
    expect(w.text()).toContain('草稿箱')
  })

  it('collapsed=true：group-label 不渲染', async () => {
    const w = await mountSidebar('/procedures/library', true)
    expect(w.findAll('.menu-group-label').length).toBe(0)
    // menu-item 仍存在（图标轨）
    expect(w.findAll('.el-menu-item').length).toBe(2)
  })

  it('在 /procedures/drafts 时 activeMenu 为 /procedures/drafts', async () => {
    const w = await mountSidebar('/procedures/drafts')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/procedures/drafts')
  })

  it('在 /procedures/:id/edit 时 activeMenu 归到 /procedures/library', async () => {
    const w = await mountSidebar('/procedures/abc123/edit')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('/procedures/library')
  })

  it('在 /settings 时 activeMenu 为空字符串（⚙ 页面不在侧栏高亮）', async () => {
    const w = await mountSidebar('/settings')
    expect((w.vm as unknown as { activeMenu: string }).activeMenu).toBe('')
  })
})
