import { beforeEach, describe, expect, it } from 'vitest'
import {
  WIZARD_KEY,
  WIZARD_TTL_MS,
  clearWizard,
  loadWizard,
  saveWizard,
  type WizardSnapshot,
} from '@/composables/useImportWizardPersistence'

function snap(createdAt: string): WizardSnapshot {
  return {
    created_at: createdAt,
    step: 3,
    upload_token: 'tok-1',
    filename: '记录控制程序.docx',
    parse_mode: 'smart',
    parse_result: null,
    tree: [],
    form: { name: '记录控制程序', folder_id: 'f1' },
  }
}

describe('导入向导 sessionStorage 持久化', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('save 后 load 回读同一快照', () => {
    const s = snap(new Date().toISOString())
    saveWizard(s)
    expect(sessionStorage.getItem(WIZARD_KEY)).toBeTruthy()
    const loaded = loadWizard()
    expect(loaded?.upload_token).toBe('tok-1')
    expect(loaded?.step).toBe(3)
  })

  it('无存储时 load 返回 null', () => {
    expect(loadWizard()).toBeNull()
  })

  it('超过 24h 的快照 load 返回 null 并清除', () => {
    const old = new Date(Date.now() - WIZARD_TTL_MS - 1000).toISOString()
    saveWizard(snap(old))
    expect(loadWizard()).toBeNull()
    expect(sessionStorage.getItem(WIZARD_KEY)).toBeNull()
  })

  it('24h 内的快照仍可恢复', () => {
    const recent = new Date(Date.now() - WIZARD_TTL_MS + 60_000).toISOString()
    saveWizard(snap(recent))
    expect(loadWizard()?.upload_token).toBe('tok-1')
  })

  it('损坏 JSON 时 load 返回 null 并清除', () => {
    sessionStorage.setItem(WIZARD_KEY, '{not json')
    expect(loadWizard()).toBeNull()
    expect(sessionStorage.getItem(WIZARD_KEY)).toBeNull()
  })

  it('clear 移除键', () => {
    saveWizard(snap(new Date().toISOString()))
    clearWizard()
    expect(sessionStorage.getItem(WIZARD_KEY)).toBeNull()
  })
})
