import { describe, expect, it } from 'vitest'
import {
  buildWizardTree,
  clearReview,
  countReview,
  deleteNode,
  findNode,
  moveNode,
  toImportNodes,
  updateNode,
} from '@/utils/importTree'
import type { ParsedNode } from '@/types/parse'

function pnode(partial: Partial<ParsedNode> & { id: string }): ParsedNode {
  return {
    id: partial.id,
    title: partial.title ?? '',
    level: partial.level ?? 1,
    order: partial.order ?? 0,
    parent_id: partial.parent_id ?? null,
    content_type: partial.content_type ?? 'chapter',
    rich_content: partial.rich_content ?? '',
    skip_numbering: partial.skip_numbering ?? false,
    confidence: partial.confidence ?? 1,
    confidence_tier: partial.confidence_tier ?? 'high',
    mark_status: partial.mark_status ?? 'unmarked',
    heading_source: partial.heading_source ?? null,
    children: partial.children ?? [],
  }
}

function sampleTree() {
  return buildWizardTree([
    pnode({
      id: 'a',
      title: '目的',
      children: [pnode({ id: 'a1', title: '正文', content_type: 'content' })],
    }),
    pnode({ id: 'b', title: '范围', mark_status: 'review', confidence_tier: 'low' }),
    pnode({ id: 'c', title: '职责' }),
  ])
}

describe('importTree 纯函数', () => {
  it('buildWizardTree 保留层级与编辑相关字段，丢弃派生字段', () => {
    const tree = sampleTree()
    expect(tree).toHaveLength(3)
    expect(tree[0].children[0].content_type).toBe('content')
    expect(tree[1].mark_status).toBe('review')
    expect(tree[1].confidence_tier).toBe('low')
    // 不应携带派生字段
    expect('order' in tree[0]).toBe(false)
    expect('level' in tree[0]).toBe(false)
  })

  it('findNode 深度查找', () => {
    const tree = sampleTree()
    expect(findNode(tree, 'a1')?.title).toBe('正文')
    expect(findNode(tree, 'zzz')).toBeNull()
  })

  it('updateNode 不可变更新指定节点', () => {
    const tree = sampleTree()
    const next = updateNode(tree, 'a', { title: '总则', skip_numbering: true })
    expect(findNode(next, 'a')?.title).toBe('总则')
    expect(findNode(next, 'a')?.skip_numbering).toBe(true)
    // 原树不变
    expect(findNode(tree, 'a')?.title).toBe('目的')
  })

  it('deleteNode 递归删除整棵子树', () => {
    const tree = sampleTree()
    const next = deleteNode(tree, 'a')
    expect(next).toHaveLength(2)
    expect(findNode(next, 'a1')).toBeNull()
  })

  it('moveNode 同级上移 / 下移，边界 no-op', () => {
    const tree = sampleTree()
    const up = moveNode(tree, 'c', -1)
    expect(up.map((n) => n.id)).toEqual(['a', 'c', 'b'])
    const down = moveNode(tree, 'a', 1)
    expect(down.map((n) => n.id)).toEqual(['b', 'a', 'c'])
    // 顶部上移 no-op
    expect(moveNode(tree, 'a', -1).map((n) => n.id)).toEqual(['a', 'b', 'c'])
    // 底部下移 no-op
    expect(moveNode(tree, 'c', 1).map((n) => n.id)).toEqual(['a', 'b', 'c'])
  })

  it('countReview 统计 review 节点', () => {
    expect(countReview(sampleTree())).toBe(1)
  })

  it('clearReview 把 review→unmarked（不动其他态）', () => {
    const cleared = clearReview(sampleTree())
    expect(countReview(cleared)).toBe(0)
    expect(findNode(cleared, 'b')?.mark_status).toBe('unmarked')
  })

  it('toImportNodes 压成导入形态并清 review', () => {
    const out = toImportNodes(sampleTree())
    expect(out[0]).toEqual({
      title: '目的',
      content_type: 'chapter',
      rich_content: '',
      skip_numbering: false,
      mark_status: 'unmarked',
      children: [
        {
          title: '正文',
          content_type: 'content',
          rich_content: '',
          skip_numbering: false,
          mark_status: 'unmarked',
          children: [],
        },
      ],
    })
    // review 节点已清
    expect(out[1].mark_status).toBe('unmarked')
    // 无 id / confidence_tier 等向导内部字段
    expect('id' in out[0]).toBe(false)
    expect('confidence_tier' in out[0]).toBe(false)
  })
})
