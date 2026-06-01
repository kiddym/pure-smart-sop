import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const { uploadAndParse } = vi.hoisted(() => ({ uploadAndParse: vi.fn() }))
const { importParsed } = vi.hoisted(() => ({ importParsed: vi.fn() }))
const { fetchFolderTree } = vi.hoisted(() => ({ fetchFolderTree: vi.fn() }))
vi.mock('@/api/parse', () => ({ uploadAndParse, importParsed }))
vi.mock('@/api/folders', () => ({ fetchFolderTree }))

import CreateFromWordDialog from '@/components/CreateFromWordDialog.vue'

// el-select 的下拉在 jsdom 里惰性挂载、内部 reactive 易递归——用极简 stub 让文件夹逻辑可测。
const SelectStub = {
  name: 'ElSelect',
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: '<div class="el-select-stub"><slot /></div>',
}
const OptionStub = {
  name: 'ElOption',
  props: { value: { type: String, default: '' }, label: { type: String, default: '' } },
  template: '<div class="el-option-stub">{{ label }}</div>',
}

const PARSED_CLEAN = { uploadToken: 'tok', parsed: { chapters: [{ id: 'c' }], warnings: [] } }
const PARSED_BLOCKING = {
  uploadToken: 'tok',
  parsed: {
    chapters: [{ id: 'c' }],
    warnings: [{ stage: 'completeness', message: '图片可能遗漏：原始 3 / 解析 1', severity: 'blocking' }],
  },
}

// 关→开切换触发 watch(visible)（非 immediate）→ 走真实的 reset + loadLeaves。
async function open(): Promise<VueWrapper> {
  const wrapper = mount(CreateFromWordDialog, {
    props: { modelValue: false },
    global: {
      plugins: [ElementPlus],
      stubs: { ElSelect: SelectStub, ElOption: OptionStub, teleport: true },
    },
    attachTo: document.body,
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

async function pickFile(wrapper: VueWrapper, name: string): Promise<File> {
  const file = new File([new Uint8Array([1])], name)
  const input = wrapper.find('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
  await input.trigger('change')
  return file
}

async function setFolder(wrapper: VueWrapper, id: string): Promise<void> {
  await wrapper.findComponent(SelectStub).vm.$emit('update:modelValue', id)
}

async function clickSubmit(wrapper: VueWrapper): Promise<void> {
  const btn = wrapper.findAll('button').find((b) => b.text().includes('导入并编辑'))
  await btn?.trigger('click')
}

describe('CreateFromWordDialog', () => {
  beforeEach(() => {
    uploadAndParse.mockReset()
    importParsed.mockReset()
    fetchFolderTree.mockReset().mockResolvedValue([])
  })

  it('打开时仅把非系统、含 prefix 的叶子文件夹填入下拉', async () => {
    fetchFolderTree.mockResolvedValue([
      { id: 'sys', full_path: '系统', system: true, prefix: 'X', children: [] },
      { id: 'f1', full_path: '根/QC', system: false, prefix: 'QC', children: [] },
      {
        id: 'mid',
        full_path: '根',
        system: false,
        prefix: '',
        children: [{ id: 'f2', full_path: '根/子', system: false, prefix: 'AB', children: [] }],
      },
    ])
    const wrapper = await open()
    // sys 系统排除；mid 非叶且无 prefix 排除 → 仅 f1、f2
    expect(wrapper.findAllComponents(OptionStub)).toHaveLength(2)
  })

  it('选文件后用文件名（去 .docx）自动填充名称', async () => {
    const wrapper = await open()
    await pickFile(wrapper, '采购控制程序.docx')
    await flushPromises()
    const nameInput = wrapper.find('input[placeholder="默认取文件名"]')
    expect((nameInput.element as HTMLInputElement).value).toBe('采购控制程序')
  })

  it('缺文件时提交：不调用 uploadAndParse', async () => {
    const wrapper = await open()
    await clickSubmit(wrapper)
    await flushPromises()
    expect(uploadAndParse).not.toHaveBeenCalled()
  })

  it('干净文档（无 blocking）：直接 import、不弹强确认、关闭对话框', async () => {
    uploadAndParse.mockResolvedValue(PARSED_CLEAN)
    importParsed.mockResolvedValue({ id: 'p9', code: 'QC-009' })
    const wrapper = await open()
    await pickFile(wrapper, '记录控制.docx')
    await setFolder(wrapper, 'f1')
    await clickSubmit(wrapper)
    await flushPromises()
    expect(importParsed).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('imported')?.[0]).toEqual(['p9'])
  })

  it('有 blocking：弹强确认且未直接 import', async () => {
    uploadAndParse.mockResolvedValue(PARSED_BLOCKING)
    importParsed.mockResolvedValue({ id: 'p9', code: 'QC-009' })
    const wrapper = await open()
    await pickFile(wrapper, '脏文档.docx')
    await setFolder(wrapper, 'f1')
    await clickSubmit(wrapper)
    await flushPromises()
    expect(importParsed).not.toHaveBeenCalled()
    expect(wrapper.findComponent({ name: 'ParseConfirmDialog' }).props('modelValue')).toBe(true)
  })

  it('blocking 后确认继续：调 importParsed 并回传全量 warnings', async () => {
    uploadAndParse.mockResolvedValue(PARSED_BLOCKING)
    importParsed.mockResolvedValue({ id: 'p9', code: 'QC-009' })
    const wrapper = await open()
    await pickFile(wrapper, '脏文档.docx')
    await setFolder(wrapper, 'f1')
    await clickSubmit(wrapper)
    await flushPromises()
    wrapper.findComponent({ name: 'ParseConfirmDialog' }).vm.$emit('confirm')
    await flushPromises()
    expect(importParsed).toHaveBeenCalledTimes(1)
    expect(importParsed.mock.calls[0][0].importNotes).toEqual(PARSED_BLOCKING.parsed.warnings)
    expect(wrapper.emitted('imported')?.[0]).toEqual(['p9'])
  })

  it('blocking 后取消：不 import、对话框保持打开', async () => {
    uploadAndParse.mockResolvedValue(PARSED_BLOCKING)
    const wrapper = await open()
    await pickFile(wrapper, '脏文档.docx')
    await setFolder(wrapper, 'f1')
    await clickSubmit(wrapper)
    await flushPromises()
    wrapper.findComponent({ name: 'ParseConfirmDialog' }).vm.$emit('cancel')
    await flushPromises()
    expect(importParsed).not.toHaveBeenCalled()
    expect(wrapper.emitted('imported')).toBeUndefined()
  })
})
