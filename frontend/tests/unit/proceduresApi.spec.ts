import { beforeEach, describe, expect, it, vi } from 'vitest'

// 用 vi.hoisted 确保 spy 在 vi.mock 工厂中可用
const { put, post } = vi.hoisted(() => ({ put: vi.fn(), post: vi.fn() }))

vi.mock('@/api/http', () => ({ http: { put, post } }))

import { transitionProcedure, updateProcedure } from '@/api/procedures'

describe('procedures api 乐观锁 If-Match', () => {
  beforeEach(() => {
    put.mockReset().mockResolvedValue({ data: {} })
    post.mockReset().mockResolvedValue({ data: {} })
  })

  it('updateProcedure 把 revision 写入 If-Match 头', async () => {
    await updateProcedure('p1', { name: 'x', level_of_use: 'reference' }, 3)
    expect(put).toHaveBeenCalledWith(
      '/procedures/p1',
      { name: 'x', level_of_use: 'reference' },
      { headers: { 'If-Match': '3' } },
    )
  })

  it('transitionProcedure 把 revision 写入 If-Match 头', async () => {
    await transitionProcedure('p1', { status: 'PUBLISHED' }, 5)
    expect(post).toHaveBeenCalledWith(
      '/procedures/p1/transition',
      { status: 'PUBLISHED' },
      { headers: { 'If-Match': '5' } },
    )
  })
})
