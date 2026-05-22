import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import TreeRow from '@/components/editor/TreeRow.vue'
import type { FlatRow } from '@/types/node'

function row(overrides: Partial<FlatRow> = {}): FlatRow {
  return {
    id: 'a',
    kind: 'chapter',
    depth: 0,
    parent_id: null,
    title: '安全须知',
    code: '1.0',
    skip_numbering: false,
    mark_status: 'unmarked',
    form_type: null,
    require_confirmation: false,
    has_children: false,
    expanded: false,
    fallback: '(未命名章节)',
    ...overrides,
  }
}

const baseProps = {
  selected: false,
  markMode: false,
  selectedForMark: false,
  addState: { canAddChapter: true, canAddContent: true, canAddStep: true },
  editable: true,
  canMoveUp: false,
  canMoveDown: false,
  dropHint: '' as const,
}

function mountRow(r: FlatRow) {
  return mount(TreeRow, { props: { row: r, ...baseProps }, global: { plugins: [ElementPlus] } })
}

describe('TreeRow', () => {
  it('显示 code 与标题', () => {
    const w = mountRow(row())
    expect(w.text()).toContain('1.0')
    expect(w.text()).toContain('安全须知')
  })

  it('标题为空时显示回退文案', () => {
    const w = mountRow(row({ title: '' }))
    expect(w.text()).toContain('(未命名章节)')
    expect(w.find('.tr-title--fallback').exists()).toBe(true)
  })

  it('点击行派发 select', async () => {
    const w = mountRow(row())
    await w.find('.tr').trigger('click')
    expect(w.emitted('select')).toBeTruthy()
  })

  it('步骤行渲染类型色条', () => {
    const w = mountRow(row({ id: 's', kind: 'step', code: '1.1', form_type: 'NUMBER', fallback: '(空步骤)' }))
    expect(w.find('.tr-typebar').exists()).toBe(true)
  })
})
