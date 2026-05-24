import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, put, del } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}))

vi.mock('@/api/http', () => ({ http: { get, post, put, delete: del } }))

import {
  listFields,
  createField,
  updateField,
  deleteField,
  updateFieldsStatus,
  batchDeleteFields,
  reorderFields,
} from '@/api/fields'

// 后端路由前缀为 /procedure-fields（见 backend/app/routers/fields.py），
// 批量操作一律 POST 子路径。这些断言锁定前后端契约，防止再次漂移。
describe('字段 api 路径/方法对齐后端 /procedure-fields*', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: [] })
    post.mockReset().mockResolvedValue({ data: {} })
    put.mockReset().mockResolvedValue({ data: {} })
    del.mockReset().mockResolvedValue({ data: null, status: 204 })
  })

  it('listFields 走 GET /procedure-fields，透传过滤参数', async () => {
    await listFields({ status: 'archived' })
    expect(get).toHaveBeenCalledWith('/procedure-fields', { params: { status: 'archived' } })
  })

  it('createField 走 POST /procedure-fields', async () => {
    const payload = { name: '供应商', key: 'supplier', field_type: 'text' as const }
    await createField(payload)
    expect(post).toHaveBeenCalledWith('/procedure-fields', payload)
  })

  it('updateField 走 PUT /procedure-fields/{id}', async () => {
    const payload = { name: '供应商' }
    await updateField('f1', payload)
    expect(put).toHaveBeenCalledWith('/procedure-fields/f1', payload)
  })

  it('deleteField 走 DELETE /procedure-fields/{id}', async () => {
    await deleteField('f1')
    expect(del).toHaveBeenCalledWith('/procedure-fields/f1')
  })

  it('updateFieldsStatus 走 POST /procedure-fields/update-status', async () => {
    await updateFieldsStatus(['f1', 'f2'], 'archived')
    expect(post).toHaveBeenCalledWith('/procedure-fields/update-status', {
      ids: ['f1', 'f2'],
      status: 'archived',
    })
  })

  it('batchDeleteFields 走 POST /procedure-fields/batch-delete', async () => {
    await batchDeleteFields(['f1', 'f2'])
    expect(post).toHaveBeenCalledWith('/procedure-fields/batch-delete', { ids: ['f1', 'f2'] })
  })

  it('reorderFields 走 POST /procedure-fields/reorder', async () => {
    await reorderFields(['f2', 'f1'])
    expect(post).toHaveBeenCalledWith('/procedure-fields/reorder', { ordered_ids: ['f2', 'f1'] })
  })
})
