import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import BlockMarkingStep from '@/components/import/BlockMarkingStep.vue'
import { buildMarkedBlocks } from '@/utils/importBlocks'
import type { ParsedImportBlock } from '@/types/parse'

function block(id: string, sourceIndex: number, text: string): ParsedImportBlock {
  return {
    id,
    source_index: sourceIndex,
    raw_text: text,
    display_text: text,
    clean_text: text,
    rich_content: `<p>${text}</p>`,
    block_type: 'paragraph',
    has_word_numbering: false,
    word_number: null,
    word_number_level: null,
    style_name: null,
    suggested_type: 'content',
    suggested_level: null,
    confidence_tier: 'low',
    mark_status: 'unmarked',
  }
}

describe('BlockMarkingStep', () => {
  it('renders blocks and emits marked updates', async () => {
    const wrapper = mount(BlockMarkingStep, {
      props: {
        modelValue: buildMarkedBlocks([block('b1', 1, '目的'), block('b2', 2, '正文')]),
      },
      global: {
        stubs: {
          'el-button': { template: '<button @click="$emit(`click`)"><slot /></button>' },
          'el-checkbox': {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<input type="checkbox" :checked="modelValue" @change="$emit(`update:modelValue`, !modelValue)" />',
          },
          'el-tag': { template: '<span><slot /></span>' },
          'el-alert': { template: '<div />' },
          'el-empty': { template: '<div />' },
        },
      },
    })

    expect(wrapper.text()).toContain('目的')
    expect(wrapper.text()).toContain('正文')

    await wrapper.find('input[type="checkbox"]').setValue(true)
    await wrapper.findAll('button').find((b) => b.text() === '一级章节')?.trigger('click')

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
  })
})
