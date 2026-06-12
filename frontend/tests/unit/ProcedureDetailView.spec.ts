import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import type { ProcedureMeta } from '@/types/procedure'

// 全量 mock 视图用到的 procedures API（只验证视图行为，不打真请求）。
const api = vi.hoisted(() => ({
  fetchProcedureDetail: vi.fn(),
  updateProcedure: vi.fn(),
  downloadPdf: vi.fn(),
  deprecateGroup: vi.fn(),
  archiveGroup: vi.fn(),
  copyProcedure: vi.fn(),
  deleteGroup: vi.fn(),
  deleteProcedure: vi.fn(),
  restoreGroup: vi.fn(),
  restorePreview: vi.fn(),
  rollbackVersion: vi.fn(),
  transitionProcedure: vi.fn(),
  upgradeVersion: vi.fn(),
}))
vi.mock('@/api/procedures', () => api)

const { default: ProcedureDetailView } = await import('@/views/procedures/ProcedureDetailView.vue')

function meta(over: Partial<ProcedureMeta> = {}): ProcedureMeta {
  return {
    id: 'p1', procedure_group_id: 'g1', code: 'AB-001', name: '设备点检', version: 1,
    is_current: true, status: 'DRAFT', folder_id: 'f1', folder_full_path: 'QC',
    description: '描述', risk_level: 1, quality_level: 1, level_of_use: 'continuous',
    custom_values: {}, version_update_notes: '', signoff_enabled: false, revision: 3,
    is_read: true, read_at: null, deprecated_from_folder_id: null, deprecated_at: null,
    archived_at: null, version_change_log: [], created_at: '', updated_at: '', import_notes: [],
    ...over,
  }
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/procedures/:id', name: 'procedure-detail', component: { template: '<div/>' } },
      { path: '/procedures/:id/edit', name: 'procedure-edit', component: { template: '<div/>' } },
      { path: '/procedures/:id/view', name: 'procedure-view', component: { template: '<div/>' } },
      { path: '/procedures/library', component: { template: '<div/>' } },
    ],
  })
}

async function mountDetail(m: ProcedureMeta) {
  api.fetchProcedureDetail.mockResolvedValue({ procedure: m, attachments: [], fields: [], has_source_docx: false })
  setActivePinia(createPinia())
  const router = makeRouter()
  await router.push('/procedures/p1')
  await router.isReady()
  const w = mount(ProcedureDetailView, {
    global: {
      plugins: [router, ElementPlus],
      stubs: {
        StatusTag: true, VersionListPanel: true, VersionActionDialog: true,
        PdfPreviewDialog: true, VersionCompareDialog: true, PublishChecklistDialog: true,
      },
    },
    attachTo: document.body,
  })
  await flushPromises()
  return w
}

// 打开「更多」下拉，返回 teleport 到 body 的菜单文本。
async function moreMenuText(w: VueWrapper): Promise<string> {
  const trigger = w.findAll('button').find((b) => b.text().includes('更多'))
  await trigger!.trigger('click')
  await flushPromises()
  return document.body.textContent ?? ''
}

beforeEach(() => {
  vi.clearAllMocks()
  document.body.innerHTML = ''
})

describe('ProcedureDetailView — 更多菜单按钮修正', () => {
  it('草稿：菜单移除「废弃」「PDF 下载」「快速编辑」，保留「PDF 预览」「程序属性」', async () => {
    const w = await mountDetail(meta({ status: 'DRAFT', is_current: true }))
    const text = await moreMenuText(w)
    expect(text).toContain('程序属性')
    expect(text).not.toContain('快速编辑')
    expect(text).toContain('PDF 预览')
    expect(text).not.toContain('PDF 下载')
    expect(text).not.toContain('废弃') // 草稿不可废弃
  })

  it('已生效（PUBLISHED 当前版）：菜单含「废弃」', async () => {
    const w = await mountDetail(meta({ status: 'PUBLISHED', is_current: true }))
    const text = await moreMenuText(w)
    expect(text).toContain('废弃')
  })

  it('canDeprecate：草稿 false，已生效当前版 true，已废止 false', async () => {
    const draft = await mountDetail(meta({ status: 'DRAFT', is_current: true }))
    expect((draft.vm as unknown as { canDeprecate: boolean }).canDeprecate).toBe(false)
    const pub = await mountDetail(meta({ status: 'PUBLISHED', is_current: true }))
    expect((pub.vm as unknown as { canDeprecate: boolean }).canDeprecate).toBe(true)
    const dep = await mountDetail(meta({ status: 'PUBLISHED', is_current: true, deprecated_at: '2026-01-01' }))
    expect((dep.vm as unknown as { canDeprecate: boolean }).canDeprecate).toBe(false)
  })
})

describe('ProcedureDetailView — 程序属性弹框', () => {
  it('弹框标题为「程序属性」，且表单不含「本次版本更新说明」字段', async () => {
    const w = await mountDetail(meta({ status: 'DRAFT', is_current: true }))
    ;(w.vm as unknown as { openEdit: () => void }).openEdit()
    await flushPromises()
    expect(document.querySelector('.el-dialog__title')?.textContent).toBe('程序属性')
    expect('version_update_notes' in (w.vm as unknown as { form: object }).form).toBe(false)
  })

  it('保存程序属性时保留 meta 原有的 version_update_notes（不被弹框清空）', async () => {
    const w = await mountDetail(meta({ status: 'DRAFT', is_current: true, version_update_notes: '保留我' }))
    api.updateProcedure.mockResolvedValue(undefined)
    ;(w.vm as unknown as { openEdit: () => void }).openEdit()
    ;(w.vm as unknown as { form: { name: string } }).form.name = '新名称'
    await (w.vm as unknown as { saveEdit: () => Promise<void> }).saveEdit()
    const payload = api.updateProcedure.mock.calls[0][1] as Record<string, unknown>
    expect(payload.name).toBe('新名称')
    expect(payload.version_update_notes).toBe('保留我')
  })
})
