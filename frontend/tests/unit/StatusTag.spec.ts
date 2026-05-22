import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StatusTag from '@/components/StatusTag.vue'

describe('StatusTag', () => {
  it('renders the published label and class', () => {
    const wrapper = mount(StatusTag, { props: { status: 'PUBLISHED' } })
    expect(wrapper.text()).toContain('已发布')
    expect(wrapper.find('.status-published').exists()).toBe(true)
  })

  it('renders the draft label and class', () => {
    const wrapper = mount(StatusTag, { props: { status: 'DRAFT' } })
    expect(wrapper.text()).toContain('草稿')
    expect(wrapper.find('.status-draft').exists()).toBe(true)
  })

  it('renders the archived label', () => {
    const wrapper = mount(StatusTag, { props: { status: 'ARCHIVED' } })
    expect(wrapper.text()).toContain('已归档')
  })
})
