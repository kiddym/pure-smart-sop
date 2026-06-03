import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const { lv, cv, uv, dv } = vi.hoisted(() => ({
  lv: vi.fn(),
  cv: vi.fn(),
  uv: vi.fn(),
  dv: vi.fn(),
}))
vi.mock('@/api/vendors', () => ({
  listVendors: lv,
  createVendor: cv,
  updateVendor: uv,
  deleteVendor: dv,
}))
vi.mock('@/api/parts', () => ({ listPartsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/assets', () => ({ listAssetsMini: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/locations', () => ({ listLocationsMini: vi.fn().mockResolvedValue([]) }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import VendorsView from '@/views/inventory/VendorsView.vue'

function mountView() {
  return mount(VendorsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lv.mockReset().mockResolvedValue([
    {
      id: 'v1',
      name: '一号供应商',
      vendor_type: '本地',
      description: '',
      rate: '4.5',
      address: '北京',
      phone: '010-111',
      email: 'a@v.com',
      website: '',
      part_ids: [],
      asset_ids: [],
      location_ids: [],
    },
  ])
  cv.mockReset().mockResolvedValue({})
  uv.mockReset().mockResolvedValue({})
  dv.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('VendorsView', () => {
  it('加载并渲染供应商行', async () => {
    const w = mountView()
    await flushPromises()
    expect(lv).toHaveBeenCalled()
    expect(w.text()).toContain('一号供应商')
    expect(w.text()).toContain('本地')
    expect(w.text()).toContain('a@v.com')
  })

  it('新建提交携带 name', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建供应商')
    expect(addBtn).toBeTruthy()
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '新供应商'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cv).toHaveBeenCalled()
    expect(cv.mock.calls[0][0]).toMatchObject({ name: '新供应商' })
  })

  it('删除经确认调用 deleteVendor', async () => {
    const { ElMessageBox } = await import('element-plus')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    const w = mountView()
    await flushPromises()
    const delBtn = w.findAll('.el-button').find((b) => b.text() === '删除')
    await delBtn!.trigger('click')
    await flushPromises()
    expect(dv).toHaveBeenCalled()
  })

  it('无权限隐藏新建/编辑/删除按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建供应商')).toBeFalsy()
    expect(w.findAll('.el-button').find((b) => b.text() === '编辑')).toBeFalsy()
    expect(w.findAll('.el-button').find((b) => b.text() === '删除')).toBeFalsy()
  })
})
