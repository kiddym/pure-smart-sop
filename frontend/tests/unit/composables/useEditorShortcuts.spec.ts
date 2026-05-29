import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent, h } from 'vue'

vi.mock('@/api/nodes', () => ({
  listNodes: vi.fn(), patchNode: vi.fn(), createNode: vi.fn(),
  deleteNode: vi.fn(), batchUpdateNodes: vi.fn(), reorderNodes: vi.fn(),
}))

import { useEditorShortcuts } from '@/composables/useEditorShortcuts'
import { useNodeEditorStore } from '@/store/nodeEditor'

let editable = true
const Harness = defineComponent({
  setup() {
    useEditorShortcuts({ editable: () => editable })
    return () => h('div')
  },
})

function press(key: string, opts: Partial<KeyboardEventInit> = {}, target?: EventTarget): KeyboardEvent {
  const e = new KeyboardEvent('keydown', { key, ctrlKey: true, bubbles: true, cancelable: true, ...opts })
  ;(target ?? window).dispatchEvent(e)
  return e
}

beforeEach(() => { setActivePinia(createPinia()); editable = true })

describe('useEditorShortcuts (E1)', () => {
  it('Ctrl+Z → undo; Ctrl+Shift+Z and Ctrl+Y → redo', () => {
    const store = useNodeEditorStore()
    const undo = vi.spyOn(store, 'undo').mockResolvedValue()
    const redo = vi.spyOn(store, 'redo').mockResolvedValue()
    mount(Harness)
    press('z')
    expect(undo).toHaveBeenCalledOnce()
    press('z', { shiftKey: true })
    press('y')
    expect(redo).toHaveBeenCalledTimes(2)
  })

  it('Ctrl+1/2/3/0 set the selected node level', () => {
    const store = useNodeEditorStore()
    store.selectedId = 'a'
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    mount(Harness)
    press('1'); press('2'); press('3'); press('0')
    expect(setLevel.mock.calls).toEqual([['a', 1], ['a', 2], ['a', 3], ['a', null]])
  })

  it('ignores shortcuts when focus is in an input or contenteditable', () => {
    const store = useNodeEditorStore()
    const undo = vi.spyOn(store, 'undo').mockResolvedValue()
    mount(Harness)
    const input = document.createElement('input')
    document.body.appendChild(input)
    press('z', {}, input)
    const ce = document.createElement('div')
    ce.setAttribute('contenteditable', 'true')
    document.body.appendChild(ce)
    press('z', {}, ce)
    expect(undo).not.toHaveBeenCalled()
    input.remove(); ce.remove()
  })

  it('no-op when not editable', () => {
    editable = false
    const store = useNodeEditorStore()
    const undo = vi.spyOn(store, 'undo').mockResolvedValue()
    mount(Harness)
    press('z')
    expect(undo).not.toHaveBeenCalled()
  })
})
