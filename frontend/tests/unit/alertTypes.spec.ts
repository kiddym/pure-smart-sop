import { describe, it, expect } from 'vitest'
import { FORM_TYPES, type FormType } from '@/types/node'
import { FORM_TYPE_META, isRichTextType, RICH_TEXT_TYPES } from '@/utils/editor'

describe('form types after alert removal', () => {
  it('FORM_TYPES 不再含 NOTE/CAUTION/WARNING', () => {
    expect(FORM_TYPES).not.toContain('NOTE' as FormType)
    expect(FORM_TYPES).not.toContain('CAUTION' as FormType)
    expect(FORM_TYPES).not.toContain('WARNING' as FormType)
  })
  it('FORM_TYPE_META 不含三警示项', () => {
    expect(Object.keys(FORM_TYPE_META)).not.toContain('WARNING')
  })
  it('富文本类型仅剩 COMMON', () => {
    expect([...RICH_TEXT_TYPES]).toEqual(['COMMON'])
    expect(isRichTextType('COMMON')).toBe(true)
    expect(isRichTextType('NUMBER')).toBe(false)
  })
})
