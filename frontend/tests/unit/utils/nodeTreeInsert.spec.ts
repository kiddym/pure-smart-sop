import { describe, expect, it } from 'vitest'
import { computeInsertIndex } from '@/utils/nodeTreeInsert'

// 派生层级：A(L1,depth0) 下挂 a1/a2(正文,depth1)，B(L1,depth0) 独立。
const nodes = [
  { id: 'A', depth: 0, heading_level: 1 },
  { id: 'a1', depth: 1, heading_level: null },
  { id: 'a2', depth: 1, heading_level: null },
  { id: 'B', depth: 0, heading_level: 1 },
]

describe('computeInsertIndex', () => {
  it('inserts a body under a chapter as its first child (right after the heading)', () => {
    expect(computeInsertIndex(nodes, 'A', null)).toBe(1)
  })

  it('inserts a sub-chapter under a chapter as its first child', () => {
    expect(computeInsertIndex(nodes, 'A', 2)).toBe(1)
  })

  it('inserts a same-level chapter after the target chapter’s whole subtree', () => {
    // 新 L1 与 A 同级 → 落到 a2 之后、B 之前，绝不窃取 A 的子节点
    expect(computeInsertIndex(nodes, 'A', 1)).toBe(3)
  })

  it('inserts a body right after a body sibling', () => {
    expect(computeInsertIndex(nodes, 'a1', null)).toBe(2)
  })

  it('inserts a chapter after a body line (shallower → after that line)', () => {
    expect(computeInsertIndex(nodes, 'a1', 1)).toBe(2)
  })

  it('falls back to append when the target id is unknown', () => {
    expect(computeInsertIndex(nodes, 'zz', null)).toBe(nodes.length)
  })
})
