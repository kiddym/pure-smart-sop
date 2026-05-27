import { describe, it, expect } from 'vitest'
import {
  computeLayerIndents,
  computeLayerUpdates,
  defaultLayerRole,
  type LayerRole,
  type LayerRow,
} from '@/utils/layerMark'

function row(id: string, kind: 'chapter' | 'step' | 'content', level: number, hasLeafChildren = false): LayerRow {
  return { id, kind, level, hasLeafChildren }
}

describe('layerMark', () => {
  it('computeLayerUpdates：一级/二级嵌套 + content 角色挂最近章节、toContentStep', () => {
    const rows = [row('a', 'chapter', 1), row('b', 'chapter', 1), row('c', 'chapter', 1)]
    const m = new Map<string, LayerRole>([
      ['a', 'chapter_1'], ['b', 'chapter_2'], ['c', 'content'],
    ])
    const u = computeLayerUpdates(rows, m)
    // TODO: Update assertions once LayerUpdate shape changes in Task 2/3
    expect((u.get('a') as any)).toEqual({ parent_id: null, toContentStep: false, sort_order: 0 })
    expect((u.get('b') as any)).toEqual({ parent_id: 'a', toContentStep: false, sort_order: 0 })
    expect((u.get('c') as any)).toEqual({ parent_id: 'b', toContentStep: true, sort_order: 0 })
  })

  it('content 行不更新 l1/l2/l3 上下文（后续 content 仍挂上一个标题）', () => {
    // a(l1) c(content) d(content)：两条 content 都挂到 a，且 content 行不改变上下文
    const rows = [row('a', 'chapter', 1), row('c', 'chapter', 2), row('d', 'chapter', 2)]
    const m = new Map<string, LayerRole>([
      ['a', 'chapter_1'], ['c', 'content'], ['d', 'content'],
    ])
    const u = computeLayerUpdates(rows, m)
    // TODO: Update assertions once LayerUpdate shape changes in Task 2/3
    expect((u.get('c') as any)).toEqual({ parent_id: 'a', toContentStep: true, sort_order: 0 })
    expect((u.get('d') as any)).toEqual({ parent_id: 'a', toContentStep: true, sort_order: 1 })
  })

  it('不可达层级夹紧：二级无一级父→根', () => {
    const rows = [row('a', 'chapter', 1)]
    const u = computeLayerUpdates(rows, new Map([['a', 'chapter_2']]))
    expect((u.get('a') as any)?.parent_id).toBeNull()
    expect((u.get('a') as any)?.toContentStep).toBe(false)
  })

  it('含叶子（步骤/内容块）子节点的行标 content 仍保持章节', () => {
    const rows = [row('a', 'chapter', 1, true)]
    const u = computeLayerUpdates(rows, new Map([['a', 'content']]))
    expect((u.get('a') as any)?.toContentStep).toBe(false)
  })

  it('computeLayerIndents：章节 = level-1，content = 当前标题层级', () => {
    const rows = [row('a', 'chapter', 1), row('b', 'chapter', 2)]
    const m = new Map<string, LayerRole>([['a', 'chapter_1'], ['b', 'content']])
    const ind = computeLayerIndents(rows, m)
    expect(ind.get('a')).toBe(0)
    expect(ind.get('b')).toBe(1)
  })

  it('defaultLayerRole with LayerRow：章节行按 level 夹到 chapter_1/2/3', () => {
    expect(defaultLayerRole({ id: 'c', kind: 'chapter', level: 1, hasLeafChildren: false })).toBe('chapter_1')
    expect(defaultLayerRole({ id: 'c', kind: 'chapter', level: 2, hasLeafChildren: false })).toBe('chapter_2')
    expect(defaultLayerRole({ id: 'c', kind: 'chapter', level: 7, hasLeafChildren: false })).toBe('chapter_3')
    expect(defaultLayerRole({ id: 'c', kind: 'chapter', level: 0, hasLeafChildren: false })).toBe('chapter_1')
  })

  it('defaultLayerRole with LayerRow：叶子行默认 keep', () => {
    expect(defaultLayerRole({ id: 's', kind: 'step', level: 0, hasLeafChildren: false })).toBe('keep')
    expect(defaultLayerRole({ id: 'c', kind: 'content', level: 0, hasLeafChildren: false })).toBe('keep')
  })
})
