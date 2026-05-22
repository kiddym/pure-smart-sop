// sessionStorage 自动保存 + 恢复（§7）。key=procedure_editor_${id}，1s debounce。
import { watchDebounced } from '@vueuse/core'
import dayjs from 'dayjs'
import { ElMessageBox } from 'element-plus'
import type { EditorDraftState } from '@/store/procedureEditor'
import type { useProcedureEditorStore } from '@/store/procedureEditor'

type EditorStore = ReturnType<typeof useProcedureEditorStore>

interface SessionDraft {
  procedure_id: string
  version: number
  revision: number
  saved_at: string
  state: EditorDraftState
}

export function useEditorPersistence(store: EditorStore, id: string) {
  const key = `procedure_editor_${id}`

  function clear(): void {
    sessionStorage.removeItem(key)
  }

  function persist(): void {
    if (!store.procedure || !store.isDirty) {
      clear()
      return
    }
    const draft: SessionDraft = {
      procedure_id: id,
      version: store.procedure.version,
      revision: store.procedure.revision,
      saved_at: new Date().toISOString(),
      state: store.exportDraft(),
    }
    sessionStorage.setItem(key, JSON.stringify(draft))
  }

  // 每次 action（节点 / 元字段变化）后 1s debounce 写入。
  function start(): void {
    watchDebounced(
      () => [store.chapters, store.steps, store.procedure, store.isDirty],
      () => persist(),
      { debounce: 1000, deep: true },
    )
  }

  async function tryRestore(): Promise<void> {
    const raw = sessionStorage.getItem(key)
    if (!raw || !store.procedure) return
    let draft: SessionDraft
    try {
      draft = JSON.parse(raw) as SessionDraft
    } catch {
      clear()
      return
    }
    if (draft.version !== store.procedure.version) {
      clear()
      return
    }
    if (draft.revision !== store.procedure.revision) {
      try {
        await ElMessageBox.confirm(
          '检测到本地未保存草稿，但远程版本已变更。是否丢弃本地草稿、使用远程最新版？',
          '草稿冲突',
          { confirmButtonText: '丢弃本地', cancelButtonText: '保留本地草稿', type: 'warning' },
        )
        clear()
        return
      } catch {
        /* 用户选择保留本地草稿 → 继续询问恢复 */
      }
    }
    try {
      await ElMessageBox.confirm(
        `检测到 ${dayjs(draft.saved_at).format('MM-DD HH:mm')} 的本地未保存草稿，是否恢复？`,
        '恢复草稿',
        { confirmButtonText: '恢复', cancelButtonText: '丢弃', type: 'info' },
      )
      store.importDraft(draft.state)
    } catch {
      clear()
    }
  }

  return { persist, clear, start, tryRestore }
}
