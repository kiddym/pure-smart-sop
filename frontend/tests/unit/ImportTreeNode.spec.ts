import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ImportTreeNode from '@/components/import/ImportTreeNode.vue'
import type { WizardNode } from '@/utils/importTree'

function node(overrides: Partial<WizardNode> = {}): WizardNode {
  return {
    id: 'a',
    title: '目的',
    content_type: 'chapter',
    rich_content: '',
    skip_numbering: false,
    mark_status: 'unmarked',
    confidence_tier: 'high',
    children: [],
    ...overrides,
  }
}

function mountNode(n: WizardNode) {
  return mount(ImportTreeNode, {
    props: { node: n, depth: 0, selectedId: null },
    global: { plugins: [ElementPlus] },
  })
}

describe('ImportTreeNode', () => {
  it('渲染标题与类型标签', () => {
    const w = mountNode(node())
    expect(w.text()).toContain('目的')
    expect(w.text()).toContain('章')
  })

  it('无标题时显示占位', () => {
    const w = mountNode(node({ title: '' }))
    expect(w.text()).toContain('（无标题）')
  })

  it('review 节点加黄色高亮 + 待确认标签', () => {
    const w = mountNode(node({ mark_status: 'review' }))
    expect(w.find('.row.review').exists()).toBe(true)
    expect(w.text()).toContain('待确认')
  })

  it('点击行派发 select', async () => {
    const w = mountNode(node())
    await w.find('.row').trigger('click')
    expect(w.emitted('select')?.[0]).toEqual(['a'])
  })

  it('递归渲染子节点', () => {
    const w = mountNode(node({ children: [node({ id: 'a1', title: '正文', content_type: 'content' })] }))
    expect(w.text()).toContain('正文')
    expect(w.text()).toContain('容')
  })
})
