import { describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ParseConfirmDialog from '@/components/ParseConfirmDialog.vue'
import type { ParseWarning } from '@/types/parse'

const WARNINGS: ParseWarning[] = [
  { stage: 'completeness', message: '图片可能遗漏：原始 3 / 解析 1', severity: 'blocking' },
  { stage: 'completeness', message: '表格可能遗漏：原始 2 / 解析 1', severity: 'blocking' },
]

// el-dialog body 惰性渲染：mount 时关闭、再 open 并 flush，内容才挂载（同 CreateFromWordDialog.spec）。
async function mountDialog(): Promise<VueWrapper> {
  const w = mount(ParseConfirmDialog, {
    props: { modelValue: false, warnings: WARNINGS },
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
    attachTo: document.body,
  })
  await w.setProps({ modelValue: true })
  await flushPromises()
  return w
}

describe('ParseConfirmDialog', () => {
  it('标题含问题条数，列出每条 message', async () => {
    const w = await mountDialog()
    expect(w.text()).toContain('2 项')
    expect(w.text()).toContain('图片可能遗漏：原始 3 / 解析 1')
    expect(w.text()).toContain('表格可能遗漏：原始 2 / 解析 1')
  })

  it('点「仍要继续导入」emit confirm', async () => {
    const w = await mountDialog()
    const btn = w.findAll('button').find((b) => b.text().includes('仍要继续'))
    await btn?.trigger('click')
    expect(w.emitted('confirm')).toBeTruthy()
  })

  it('点「取消导入」emit cancel', async () => {
    const w = await mountDialog()
    const btn = w.findAll('button').find((b) => b.text().includes('取消导入'))
    await btn?.trigger('click')
    expect(w.emitted('cancel')).toBeTruthy()
  })
})
