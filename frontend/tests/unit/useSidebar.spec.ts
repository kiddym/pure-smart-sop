import { describe, it, expect, beforeEach } from 'vitest'
import { useSidebar } from '@/composables/useSidebar'

beforeEach(() => {
  localStorage.clear()
  // 模块级单例：上条用例可能改过，显式复位再测
  useSidebar().collapsed.value = false
})

describe('useSidebar', () => {
  it('toggle 翻转 collapsed', () => {
    const { collapsed, toggle } = useSidebar()
    expect(collapsed.value).toBe(false)
    toggle()
    expect(collapsed.value).toBe(true)
    toggle()
    expect(collapsed.value).toBe(false)
  })

  it('collapsed 变更落盘 localStorage', () => {
    const { toggle } = useSidebar()
    toggle()
    expect(localStorage.getItem('smartsop.sidebar.collapsed')).toBe('true')
  })

  it('模块级单例：多次调用共享同一 ref', () => {
    const a = useSidebar()
    const b = useSidebar()
    a.toggle()
    expect(b.collapsed.value).toBe(true)
  })
})
