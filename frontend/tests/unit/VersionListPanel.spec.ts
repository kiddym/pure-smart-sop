import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const { fetchGroupVersions } = vi.hoisted(() => ({ fetchGroupVersions: vi.fn() }))
vi.mock('@/api/procedures', () => ({ fetchGroupVersions }))

import VersionListPanel from '@/components/version/VersionListPanel.vue'
import type { VersionListItem } from '@/types/procedure'

function item(o: Partial<VersionListItem> & { id: string; version: number }): VersionListItem {
  return {
    id: o.id,
    version: o.version,
    status: o.status ?? 'ARCHIVED',
    is_current: o.is_current ?? false,
    version_update_notes: o.version_update_notes ?? '',
    version_update_notes_preview: o.version_update_notes_preview ?? '',
    created_at: o.created_at ?? '2026-05-22T00:00:00',
    archived_at: o.archived_at ?? null,
  }
}

async function mountPanel(items: VersionListItem[], viewingId = 'v3') {
  fetchGroupVersions.mockResolvedValue({ count: items.length, items })
  const w = mount(VersionListPanel, {
    props: { groupId: 'g1', viewingId },
    global: { plugins: [ElementPlus] },
  })
  await flushPromises()
  return w
}

describe('VersionListPanel', () => {
  beforeEach(() => fetchGroupVersions.mockReset())

  it('渲染全部版本行 + 当前标记', async () => {
    const w = await mountPanel([
      item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true }),
      item({ id: 'v2', version: 2 }),
      item({ id: 'v1', version: 1 }),
    ])
    expect(w.text()).toContain('v3')
    expect(w.text()).toContain('v1')
    expect(w.text()).toContain('当前')
  })

  it('存在当前已发布版本时，归档版本显示「回退到此版本」并带当前 id 派发', async () => {
    const w = await mountPanel([
      item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true }),
      item({ id: 'v2', version: 2, status: 'ARCHIVED' }),
    ])
    const rollbackBtn = w.findAll('button').find((b) => b.text().includes('回退到此版本'))
    expect(rollbackBtn).toBeTruthy()
    await rollbackBtn!.trigger('click')
    expect(w.emitted('rollback')?.[0]).toEqual([2, 'v3'])
  })

  it('当前版本为草稿时不提供回退', async () => {
    const w = await mountPanel([
      item({ id: 'v2', version: 2, status: 'DRAFT', is_current: true }),
      item({ id: 'v1', version: 1, status: 'ARCHIVED' }),
    ])
    expect(w.findAll('button').some((b) => b.text().includes('回退到此版本'))).toBe(false)
  })

  it('点击查看派发 view（非当前查看行）', async () => {
    const w = await mountPanel(
      [
        item({ id: 'v3', version: 3, status: 'PUBLISHED', is_current: true }),
        item({ id: 'v2', version: 2 }),
      ],
      'v3',
    )
    const viewBtn = w.findAll('button').find((b) => b.text().trim() === '查看')
    await viewBtn!.trigger('click')
    expect(w.emitted('view')?.[0]).toEqual(['v2'])
  })
})
