import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get, post, del } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), del: vi.fn() }))

vi.mock('@/api/http', () => ({ http: { get, post, delete: del } }))

import {
  copyProcedure,
  deleteGroup,
  deleteProcedure,
  deprecateGroup,
  fetchGroupVersions,
  restoreGroup,
  restorePreview,
  rollbackVersion,
  upgradeVersion,
} from '@/api/procedures'

describe('版本管理 api（Phase 7）', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: {} })
    post.mockReset().mockResolvedValue({ data: {} })
    del.mockReset().mockResolvedValue({ data: null, status: 204 })
  })

  it('upgradeVersion 走 POST /upgrade-version，无 If-Match', async () => {
    await upgradeVersion('p1')
    expect(post).toHaveBeenCalledWith('/procedures/p1/upgrade-version')
  })

  it('rollbackVersion 提交 target_version + reason', async () => {
    await rollbackVersion('p1', { target_version: 2, reason: '回退到稳定版' })
    expect(post).toHaveBeenCalledWith('/procedures/p1/rollback', {
      target_version: 2,
      reason: '回退到稳定版',
    })
  })

  it('deprecateGroup 提交 reason', async () => {
    await deprecateGroup('p1', '停用')
    expect(post).toHaveBeenCalledWith('/procedures/p1/deprecate', { reason: '停用' })
  })

  it('restorePreview 走 GET /restore-preview', async () => {
    get.mockResolvedValue({ data: { folder_exists: true, version_count: 2 } })
    const out = await restorePreview('p1')
    expect(get).toHaveBeenCalledWith('/procedures/p1/restore-preview')
    expect(out.folder_exists).toBe(true)
  })

  it('restoreGroup 提交 reason + 可选 target_folder_id', async () => {
    await restoreGroup('p1', { reason: '恢复', target_folder_id: 'f9' })
    expect(post).toHaveBeenCalledWith('/procedures/p1/restore', {
      reason: '恢复',
      target_folder_id: 'f9',
    })
  })

  it('copyProcedure 提交 target_folder_id + name', async () => {
    await copyProcedure('p1', { target_folder_id: 'f2', name: '副本' })
    expect(post).toHaveBeenCalledWith('/procedures/p1/copy', {
      target_folder_id: 'f2',
      name: '副本',
    })
  })

  it('fetchGroupVersions 走 GET /procedure-groups/{id}/versions', async () => {
    get.mockResolvedValue({ data: { count: 3, items: [] } })
    const out = await fetchGroupVersions('g1')
    expect(get).toHaveBeenCalledWith('/procedure-groups/g1/versions', { params: { count_only: false } })
    expect(out.count).toBe(3)
  })

  it('deleteGroup 携 reason 体', async () => {
    await deleteGroup('g1', '空草稿组删除')
    expect(del).toHaveBeenCalledWith('/procedure-groups/g1', { data: { reason: '空草稿组删除' } })
  })

  it('deleteProcedure 普通软删（204）返回 null', async () => {
    del.mockResolvedValue({ data: '', status: 204 })
    const r = await deleteProcedure('p1', '删')
    expect(del).toHaveBeenCalledWith('/procedures/p1', { data: { reason: '删' } })
    expect(r).toBeNull()
  })

  it('deleteProcedure 丢弃 DRAFT（200）返回 DiscardDraftResult', async () => {
    del.mockResolvedValue({
      data: { deleted_id: 'p1', new_current_id: 'p0', new_current_version: 1 },
      status: 200,
    })
    const r = await deleteProcedure('p1', '丢弃草稿')
    expect(r).toEqual({ deleted_id: 'p1', new_current_id: 'p0', new_current_version: 1 })
  })
})
