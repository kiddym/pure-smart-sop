import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import CollapsiblePanel from '@/components/shared/CollapsiblePanel.vue'
import type { PanelConfig } from '@/utils/collapsiblePanel'

const cfg: PanelConfig = { defaultWidth: 360, min: 300, max: 700 }
const stubs = {
  ImportSideRail: {
    props: ['label', 'side'],
    emits: ['expand'],
    template: '<div class="stub-rail" :data-side="side" @click="$emit(\'expand\')">{{ label }}</div>',
  },
}

function mountPanel(side: 'left' | 'right', storageKey = `k-${side}`) {
  return mount(CollapsiblePanel, {
    props: { label: '节点详情', side, storageKey, config: cfg },
    slots: { default: '<div class="stub-content">X</div>' },
    global: { stubs },
  })
}

beforeEach(() => localStorage.clear())

describe('CollapsiblePanel', () => {
  it('展开态渲染 slot 内容、不渲染 rail', () => {
    const w = mountPanel('right')
    expect(w.find('.stub-content').exists()).toBe(true)
    expect(w.find('.stub-rail').exists()).toBe(false)
  })

  it('点折叠按钮 → 显示 rail；点 rail → 还原 slot', async () => {
    const w = mountPanel('right')
    await w.get('.collapse-btn').trigger('click')
    expect(w.find('.stub-rail').exists()).toBe(true)
    expect(w.find('.stub-content').exists()).toBe(false)
    await w.get('.stub-rail').trigger('click')
    expect(w.find('.stub-content').exists()).toBe(true)
  })

  it('side=left → 折叠箭头 «、splitter 在右缘', () => {
    const w = mountPanel('left')
    expect(w.get('.collapse-btn').text()).toBe('«')
    expect(w.find('.splitter-right').exists()).toBe(true)
  })

  it('side=right → 折叠箭头 »、splitter 在左缘', () => {
    const w = mountPanel('right')
    expect(w.get('.collapse-btn').text()).toBe('»')
    expect(w.find('.splitter-left').exists()).toBe(true)
  })

  it('折叠态把 side 透传给 rail', async () => {
    const w = mountPanel('right')
    await w.get('.collapse-btn').trigger('click')
    expect(w.get('.stub-rail').attributes('data-side')).toBe('right')
  })
})
