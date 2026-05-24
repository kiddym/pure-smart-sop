import { describe, expect, it } from 'vitest'
import { applyLayerRole, computeChapterNumbers, computeLevelMap } from '@/utils/importTree'
import type { WizardNode } from '@/utils/importTree'

function wnode(p: Partial<WizardNode> & { id: string }): WizardNode {
  const content_type = p.content_type ?? 'chapter'
  return {
    id: p.id,
    title: p.title ?? p.id,
    content_type,
    rich_content: p.rich_content ?? (content_type === 'content' ? `<p>${p.id}</p>` : ''),
    skip_numbering: p.skip_numbering ?? content_type === 'content',
    mark_status: p.mark_status ?? 'unmarked',
    confidence_tier: p.confidence_tier ?? 'high',
    children: p.children ?? [],
  }
}

function levels(tree: WizardNode[]): Record<string, number> {
  return Object.fromEntries(computeLevelMap(tree))
}

function find(tree: WizardNode[], id: string): WizardNode | undefined {
  for (const n of tree) {
    if (n.id === id) return n
    const hit = find(n.children, id)
    if (hit) return hit
  }
  return undefined
}

describe('applyLayerRole 层级标定（重建语义）', () => {
  it('顺序无关：勾选 C、B（任意点选顺序）都标二级 → 两者都在 A 下、同为二级', () => {
    const tree = [wnode({ id: 'A' }), wnode({ id: 'B' }), wnode({ id: 'C' })]
    const out = applyLayerRole(tree, ['C', 'B'], 'chapter_2')
    const L = levels(out)
    expect({ B: L.B, C: L.C }).toEqual({ B: 2, C: 2 })
    expect(find(out, 'A')?.children.map((n) => n.id)).toEqual(['B', 'C'])
  })

  it('首节点标二级：无可挂父，夹紧为一级且不崩、不影响其他节点', () => {
    const tree = [wnode({ id: 'A' }), wnode({ id: 'B' })]
    const out = applyLayerRole(tree, ['A'], 'chapter_2')
    expect(out.map((n) => n.id)).toEqual(['A', 'B'])
    expect(levels(out).A).toBe(1)
  })

  it('够不到目标层级（标三级但只有一级父）：夹紧到可达层级并挂在正确父下', () => {
    const tree = [wnode({ id: 'A' }), wnode({ id: 'B' })]
    const out = applyLayerRole(tree, ['B'], 'chapter_3')
    expect(levels(out).B).toBe(2)
    expect(find(out, 'A')?.children.map((n) => n.id)).toEqual(['B'])
  })

  it('绝不把章节塞进正文节点：前驱是 content 时夹紧为根级章节并能拿到编号', () => {
    const tree = [wnode({ id: 'X', content_type: 'content' }), wnode({ id: 'B' })]
    const out = applyLayerRole(tree, ['B'], 'chapter_2')
    const x = find(out, 'X')
    expect(x?.children.some((c) => c.id === 'B')).toBe(false)
    expect(levels(out).B).toBe(1)
    expect(computeChapterNumbers(out).B).toBeTruthy()
  })

  it('子树整体平移：B 降为二级时其子 C 同步变三级（保持父子关系）', () => {
    const tree = [
      wnode({ id: 'A' }),
      wnode({ id: 'B', children: [wnode({ id: 'C' })] }),
    ]
    const out = applyLayerRole(tree, ['B'], 'chapter_2')
    const L = levels(out)
    expect({ B: L.B, C: L.C }).toEqual({ B: 2, C: 3 })
    expect(find(out, 'B')?.children.map((n) => n.id)).toEqual(['C'])
  })

  it('内容升级为章节：文本转为标题、清空正文、不丢数据', () => {
    const tree = [
      wnode({ id: 'A' }),
      wnode({ id: 'X', content_type: 'content', title: '', rich_content: '<p>操作步骤</p>' }),
    ]
    const out = applyLayerRole(tree, ['X'], 'chapter_2')
    const x = find(out, 'X')
    expect(x?.content_type).toBe('chapter')
    expect(levels(out).X).toBe(2)
    expect(x?.title).toBe('操作步骤')
    expect(x?.rich_content).toBe('')
  })

  it('章节降级为正文：标题文本转入正文不丢，原章节子节点重挂为根章节', () => {
    const tree = [
      wnode({ id: 'A', title: '操作', children: [wnode({ id: 'B' })] }),
    ]
    const out = applyLayerRole(tree, ['A'], 'content')
    const a = find(out, 'A')
    expect(a?.content_type).toBe('content')
    expect(a?.rich_content).toContain('操作')
    // 子节点 B 不丢，且仍是章节
    const b = find(out, 'B')
    expect(b?.content_type).toBe('chapter')
  })

  it('既有可用路径不回归：嵌套节点标一级 → 提升到根', () => {
    const tree = [wnode({ id: 'a', children: [wnode({ id: 'a1' })] })]
    const out = applyLayerRole(tree, ['a1'], 'chapter_1')
    expect(out.map((n) => n.id)).toEqual(['a', 'a1'])
  })
})
