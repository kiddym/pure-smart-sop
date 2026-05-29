import { onMounted, onUnmounted } from 'vue'
import { useNodeEditorStore } from '@/store/nodeEditor'

// 节点编辑器键盘快捷键（E1）：撤销/重做 + 设标题层级。
// 取代随旧编辑器删除的 useEditorKeyboard（节点模型版）。
// 聚焦守卫：焦点在 input/textarea/select 或 contenteditable（含 wangeditor 正文）内时
// 不接管，交还原生处理（含富文本自身的文本撤销）。
export function useEditorShortcuts(opts: { editable: () => boolean }): void {
  const store = useNodeEditorStore()

  function inEditableField(el: EventTarget | null): boolean {
    if (!(el instanceof HTMLElement)) return false
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') return true
    if (el.isContentEditable) return true
    return el.closest('[contenteditable="true"]') !== null
  }

  function onKeydown(e: KeyboardEvent): void {
    if (!opts.editable()) return
    if (inEditableField(e.target)) return
    const mod = e.metaKey || e.ctrlKey
    if (!mod) return
    const key = e.key.toLowerCase()

    if (key === 'z' && !e.shiftKey) {
      e.preventDefault()
      void store.undo()
    } else if ((key === 'z' && e.shiftKey) || key === 'y') {
      e.preventDefault()
      void store.redo()
    } else if (key === '1' || key === '2' || key === '3' || key === '0') {
      if (!store.selectedId) return
      e.preventDefault()
      void store.setLevel(store.selectedId, key === '0' ? null : Number(key))
    }
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onUnmounted(() => window.removeEventListener('keydown', onKeydown))
}
