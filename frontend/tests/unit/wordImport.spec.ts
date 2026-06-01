import { describe, it, expect, vi, beforeEach } from 'vitest'

const post = vi.hoisted(() => vi.fn())
vi.mock('@/api/http', () => ({ http: { post, get: vi.fn() } }))

import { uploadAndParse, importParsed } from '@/api/parse'
import type { ParseWarning } from '@/types/parse'

beforeEach(() => {
  post.mockReset()
  post.mockImplementation((url: string) => {
    if (url === '/uploads') return Promise.resolve({ data: { upload_token: 'tok', filename: 'a.docx' } })
    if (url === '/parse') return Promise.resolve({ data: { chapters: [{ id: 'c', title: 'X' }], warnings: [] } })
    if (url === '/procedures/import') return Promise.resolve({ data: { id: 'p1', code: 'QC-1' } })
    return Promise.reject(new Error('unexpected ' + url))
  })
})

describe('uploadAndParse', () => {
  it('upload→parse，返回 token 与 parsed', async () => {
    const file = new File(['x'], 'a.docx')
    const { uploadToken, parsed } = await uploadAndParse(file)
    expect(uploadToken).toBe('tok')
    expect(parsed.chapters).toHaveLength(1)
    expect(post.mock.calls.map((c) => c[0])).toEqual(['/uploads', '/parse'])
  })
})

describe('importParsed', () => {
  it('调 /procedures/import，回传 chapters 与 import_notes', async () => {
    const notes: ParseWarning[] = [{ stage: 'completeness', message: '缺图', severity: 'blocking' }]
    const proc = await importParsed({
      uploadToken: 'tok',
      folderId: 'f1',
      name: '我的程序',
      chapters: [{ id: 'c' }] as never,
      importNotes: notes,
    })
    expect(proc.id).toBe('p1')
    const body = post.mock.calls.find((c) => c[0] === '/procedures/import')![1]
    expect(body).toMatchObject({ name: '我的程序', folder_id: 'f1', upload_token: 'tok' })
    expect(body.import_notes).toEqual(notes)
  })
})
