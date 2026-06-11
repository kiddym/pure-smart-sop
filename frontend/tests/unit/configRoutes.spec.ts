import { describe, it, expect } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { routes } from '@/router/routes'

function makeRouter() {
  return createRouter({ history: createMemoryHistory(), routes })
}

describe('组织设置路由', () => {
  it('新增 /admin/config/organization 可解析且 name 为 config-organization', async () => {
    const r = makeRouter()
    await r.push('/admin/config/organization')
    expect(r.currentRoute.value.matched.length).toBeGreaterThan(0)
    expect(r.currentRoute.value.name).toBe('config-organization')
  })

  it('旧设置路由 redirect 到聚合页对应 tab', async () => {
    const cases: [string, string][] = [
      ['/admin/company', 'company'],
      ['/admin/settings', 'global'],
    ]
    const r = makeRouter()
    for (const [from, tab] of cases) {
      await r.push(from)
      expect(r.currentRoute.value.path).toBe('/admin/config/organization')
      expect(r.currentRoute.value.query.tab).toBe(tab)
    }
  })

  it('既有别名 redirect 双跳仍达组织设置', async () => {
    const r = makeRouter()
    await r.push('/platform/settings') // → /admin/company → ?tab=company
    expect(r.currentRoute.value.path).toBe('/admin/config/organization')
    expect(r.currentRoute.value.query.tab).toBe('company')
    await r.push('/settings') // → /admin/settings → ?tab=global
    expect(r.currentRoute.value.path).toBe('/admin/config/organization')
    expect(r.currentRoute.value.query.tab).toBe('global')
  })

})

describe('配置中心路由', () => {
  it('Hub 与 SOP 聚合页路由可解析', async () => {
    const r = makeRouter()
    for (const p of ['/admin/config', '/admin/config/sop']) {
      await r.push(p)
      expect(r.currentRoute.value.matched.length).toBeGreaterThan(0)
    }
  })

  it('旧字段路由 redirect 到聚合页对应 tab', async () => {
    const cases: [string, string, string | undefined][] = [
      ['/admin/fields', '/admin/config/sop', 'fields'],
      ['/admin/heading-rules', '/admin/config/sop', 'heading-rules'],
    ]
    const r = makeRouter()
    for (const [from, path, tab] of cases) {
      await r.push(from)
      expect(r.currentRoute.value.path).toBe(path)
      if (tab) expect(r.currentRoute.value.query.tab).toBe(tab)
    }
  })
})
