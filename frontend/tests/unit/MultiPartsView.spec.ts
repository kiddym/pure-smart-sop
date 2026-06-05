import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

// 保留真实 element-plus（组件渲染要用），仅替换 ElMessageBox.confirm（删除确认）。
vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal<typeof import('element-plus')>()
  return { ...actual, ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm' as never) } }
})

const { lmp, cmp, ump, dmp } = vi.hoisted(() => ({
  lmp: vi.fn(),
  cmp: vi.fn(),
  ump: vi.fn(),
  dmp: vi.fn(),
}))
vi.mock('@/api/multiParts', () => ({
  listMultiParts: lmp,
  getMultiPart: vi.fn(),
  createMultiPart: cmp,
  updateMultiPart: ump,
  deleteMultiPart: dmp,
}))
const { lpm } = vi.hoisted(() => ({ lpm: vi.fn() }))
vi.mock('@/api/parts', () => ({ listPartsMini: lpm }))

const authState = vi.hoisted(() => ({ can: true }))
vi.mock('@/store/auth', () => ({
  useAuthStore: () => ({ hasPermission: () => authState.can, user: { role_code: 'admin' } }),
}))

import { ElMessageBox } from 'element-plus'
import MultiPartsView from '@/views/inventory/MultiPartsView.vue'

function mountView() {
  return mount(MultiPartsView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

beforeEach(() => {
  setActivePinia(createPinia())
  authState.can = true
  lmp.mockReset().mockResolvedValue([
    { id: 'k1', custom_id: 'KIT-001', name: '泵维修套件', description: '常用', part_ids: ['p1', 'p2'] },
  ])
  lpm.mockReset().mockResolvedValue([
    { id: 'p1', custom_id: 'P-001', name: '螺栓' },
    { id: 'p2', custom_id: 'P-002', name: '垫片' },
  ])
  cmp.mockReset().mockResolvedValue({})
  ump.mockReset().mockResolvedValue({})
  dmp.mockReset().mockResolvedValue(undefined)
  vi.mocked(ElMessageBox.confirm).mockReset().mockResolvedValue('confirm' as never)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MultiPartsView', () => {
  it('加载并渲染套件 + 成员数', async () => {
    const w = mountView()
    await flushPromises()
    expect(lmp).toHaveBeenCalled()
    expect(lpm).toHaveBeenCalled()
    expect(w.text()).toContain('KIT-001')
    expect(w.text()).toContain('泵维修套件')
    expect(w.text()).toContain('2 项')
  })

  it('memberLabel 映射成员名，未知 id 占位', async () => {
    const w = mountView()
    await flushPromises()
    const vm = w.vm as unknown as { memberLabel: (id: string) => string }
    expect(vm.memberLabel('p1')).toBe('P-001 螺栓')
    expect(vm.memberLabel('zzz')).toBe('(已删除)')
  })

  it('新建提交携带 name + part_ids', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建套件')
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '新套件'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const vm = w.vm as unknown as { form: { part_ids: string[] } }
    vm.form.part_ids = ['p1']
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cmp).toHaveBeenCalled()
    expect(cmp.mock.calls[0][0]).toMatchObject({ name: '新套件', part_ids: ['p1'] })
  })

  it('编辑回填并提交 updateMultiPart', async () => {
    const w = mountView()
    await flushPromises()
    const editBtn = w.findAll('.el-button').find((b) => b.text() === '编辑')
    await editBtn!.trigger('click')
    await flushPromises()
    const vm = w.vm as unknown as { form: { name: string; part_ids: string[] } }
    expect(vm.form.name).toBe('泵维修套件')
    expect(vm.form.part_ids).toEqual(['p1', 'p2'])
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(ump).toHaveBeenCalledWith('k1', expect.objectContaining({ name: '泵维修套件' }))
  })

  it('删除确认后调用 deleteMultiPart', async () => {
    const w = mountView()
    await flushPromises()
    const delBtn = w.findAll('.el-button').find((b) => b.text() === '删除')
    await delBtn!.trigger('click')
    await flushPromises()
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(dmp).toHaveBeenCalledWith('k1')
  })

  it('空成员套件可提交（part_ids 为空）', async () => {
    const w = mountView()
    await flushPromises()
    const addBtn = w.findAll('.el-button').find((b) => b.text() === '新建套件')
    await addBtn!.trigger('click')
    await flushPromises()
    const nameInput = document.querySelector(
      '.el-dialog input[placeholder="请输入名称"]',
    ) as HTMLInputElement
    nameInput.value = '空套件'
    nameInput.dispatchEvent(new Event('input'))
    await flushPromises()
    const saveBtn = Array.from(document.querySelectorAll('.el-dialog .el-button')).find(
      (b) => b.textContent?.trim() === '保存',
    ) as HTMLElement
    saveBtn.click()
    await flushPromises()
    expect(cmp).toHaveBeenCalled()
    expect(cmp.mock.calls[0][0]).toMatchObject({ name: '空套件', part_ids: [] })
  })

  it('无 part.create 隐藏新建按钮', async () => {
    authState.can = false
    const w = mountView()
    await flushPromises()
    expect(w.findAll('.el-button').find((b) => b.text() === '新建套件')).toBeFalsy()
  })
})
