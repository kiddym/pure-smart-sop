import { describe, it, expect } from 'vitest'
import { nextReviewId, nextRowId } from '@/utils/reviewNav'

const rows = [
  { id: 'a', mark_status: 'unmarked' as const },
  { id: 'b', mark_status: 'review' as const },
  { id: 'c', mark_status: 'review' as const },
  { id: 'd', mark_status: 'unmarked' as const },
]

describe('nextReviewId', () => {
  it('无选中 → 第一个 review', () => {
    expect(nextReviewId(rows, null)).toBe('b')
  })
  it('从某 review → 下一个 review', () => {
    expect(nextReviewId(rows, 'b')).toBe('c')
  })
  it('最后一个 review → 循环回第一个', () => {
    expect(nextReviewId(rows, 'c')).toBe('b')
  })
  it('当前在非 review 行 → 文档序之后的第一个 review（环绕）', () => {
    expect(nextReviewId(rows, 'd')).toBe('b')
  })
  it('无 review → null', () => {
    expect(nextReviewId([{ id: 'a', mark_status: 'unmarked' as const }], 'a')).toBeNull()
  })
  it('content 类型的 review 节点同样进入复查导航（按 mark_status，类型无关）', () => {
    // 含公式/SmartArt/chart 占位的 content 节点 mark_status='review'（B 项）。
    // 复查导航不应按节点类型把 content 过滤掉。
    const mixed = [
      { id: 's1', content_type: 'step', mark_status: 'unmarked' as const },
      { id: 'c1', content_type: 'content', mark_status: 'review' as const },
      { id: 'h1', content_type: 'chapter', mark_status: 'unmarked' as const },
    ]
    expect(nextReviewId(mixed, null)).toBe('c1')
    expect(nextReviewId(mixed, 's1')).toBe('c1')
  })
})

describe('nextRowId（通用谓词导航）', () => {
  const rows = [
    { id: 'a', kind: 'chapter', title: '有标题' },
    { id: 'b', kind: 'chapter', title: '' },
    { id: 'c', kind: 'content', title: '' }, // 内容块空标题不应命中 chapter 谓词
    { id: 'd', kind: 'chapter', title: '   ' }, // 纯空白视为空
  ]
  const isMissing = (r: { kind: string; title: string }) => r.kind === 'chapter' && !r.title.trim()

  it('无选中 → 第一个命中', () => {
    expect(nextRowId(rows, null, isMissing)).toBe('b')
  })
  it('从某命中 → 下一个命中（跳过非命中、环绕）', () => {
    expect(nextRowId(rows, 'b', isMissing)).toBe('d')
  })
  it('最后一个命中 → 环绕回第一个', () => {
    expect(nextRowId(rows, 'd', isMissing)).toBe('b')
  })
  it('无命中 → null', () => {
    expect(nextRowId(rows, null, () => false)).toBeNull()
  })
})
