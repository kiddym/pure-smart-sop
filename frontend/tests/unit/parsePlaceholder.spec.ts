import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

const Host = {
  props: { html: { type: String, default: '' } },
  template: '<div class="content-node" v-html="html" />',
}

describe('sop-ph 占位渲染', () => {
  it('formula 占位渲染为带 class 的 span', () => {
    const w = mount(Host, { props: { html: '<p><span class="sop-ph" data-ph="formula">[公式]</span></p>' } })
    const ph = w.find('span.sop-ph')
    expect(ph.exists()).toBe(true)
    expect(ph.attributes('data-ph')).toBe('formula')
    expect(ph.text()).toBe('[公式]')
  })
  it('chart 占位渲染为带 class 的 div', () => {
    const w = mount(Host, { props: { html: '<div class="sop-ph" data-ph="chart">[图表]</div>' } })
    expect(w.find('div.sop-ph[data-ph="chart"]').exists()).toBe(true)
  })
  it('vector 占位渲染为带 class 的 div', () => {
    const w = mount(Host, { props: { html: '<div class="sop-ph" data-ph="vector">[矢量图无法转换]</div>' } })
    const ph = w.find('div.sop-ph[data-ph="vector"]')
    expect(ph.exists()).toBe(true)
    expect(ph.text()).toBe('[矢量图无法转换]')
  })
})
