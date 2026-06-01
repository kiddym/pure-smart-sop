import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ParseNoticeBar from '@/components/editor/ParseNoticeBar.vue'
import type { ParseWarning } from '@/types/parse'

const NOTES: ParseWarning[] = [
  { stage: 'completeness', message: '图片可能遗漏：原始 3 / 解析 1', severity: 'blocking' },
  { stage: 'discarded_by_design', message: '已忽略 1 处页眉/页脚', severity: 'info' },
]

function mountBar(notes: ParseWarning[]) {
  return mount(ParseNoticeBar, {
    props: { notes },
    global: { plugins: [ElementPlus] },
  })
}

describe('ParseNoticeBar', () => {
  it('空数组不渲染', () => {
    const w = mountBar([])
    expect(w.text()).toBe('')
  })

  it('渲染条数、blocking 标已放行、info 普通', async () => {
    const w = mountBar(NOTES)
    // 展开后才显示明细
    const head = w.find('.pn-head')
    await head.trigger('click')
    expect(w.text()).toContain('解析提示 2 条')
    expect(w.text()).toContain('已知缺失（已放行）')
    expect(w.text()).toContain('图片可能遗漏：原始 3 / 解析 1')
    expect(w.text()).toContain('已忽略 1 处页眉/页脚')
  })
})
