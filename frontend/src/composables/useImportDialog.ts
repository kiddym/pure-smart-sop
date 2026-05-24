import { computed, reactive, ref } from 'vue'
import type { ParseResponse } from '@/types/parse'
import type { ContentType, MarkStatus } from '@/types/node'
import {
  addChildNode,
  addSiblingNode,
  applyLayerRole,
  buildWizardTree,
  computeChapterNumbers,
  computeLevelMap,
  countReview,
  deleteNode,
  demoteNode,
  extractIgnored,
  findNode,
  moveNode,
  promoteNode,
  restoreFromIgnored,
  setMarkStatus,
  updateNode,
  type WizardNode,
} from '@/utils/importTree'

export type ImportDialogMode = 'normal' | 'layer-marking' | 'step-annotation'
type LayerRole = 'chapter_1' | 'chapter_2' | 'chapter_3' | 'content' | 'ignored'

export function useImportDialog() {
  // ---- 文件 / 解析 ---- //
  const file = ref<File | null>(null)
  const uploadToken = ref('')
  const filename = ref('')
  const parseResult = ref<ParseResponse | null>(null)

  // ---- 树状态 ---- //
  const tree = ref<WizardNode[]>([])
  const ignored = ref<WizardNode[]>([])
  const selectedId = ref<string | null>(null)

  // ---- 模式 / 标记选择 ---- //
  const mode = ref<ImportDialogMode>('normal')
  const markSelection = ref<Set<string>>(new Set())

  // ---- 表单 ---- //
  const form = reactive({ name: '', folder_id: '' })

  // ---- 派生 ---- //
  const selected = computed(() => (selectedId.value ? findNode(tree.value, selectedId.value) : null))
  const levelMap = computed(() => computeLevelMap(tree.value))
  const numberMap = computed(() => computeChapterNumbers(tree.value))
  const reviewCount = computed(() => countReview(tree.value))

  // ---- 模式切换 ---- //
  function exitMode(): void {
    mode.value = 'normal'
    markSelection.value = new Set()
  }

  function toggleLayerMarking(): void {
    if (mode.value === 'layer-marking') exitMode()
    else {
      mode.value = 'layer-marking'
      markSelection.value = new Set()
    }
  }

  function toggleStepAnnotation(): void {
    if (mode.value === 'step-annotation') exitMode()
    else {
      mode.value = 'step-annotation'
      markSelection.value = new Set()
    }
  }

  function toggleMarkSelection(id: string): void {
    const next = new Set(markSelection.value)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    markSelection.value = next
  }

  function clearMarkSelection(): void {
    markSelection.value = new Set()
  }

  // ---- 装载 / 树编辑 ---- //
  function loadParseResult(res: ParseResponse): void {
    parseResult.value = res
    tree.value = buildWizardTree(res.chapters)
    ignored.value = []
    selectedId.value = null
    if (!form.name) {
      form.name = filename.value.replace(/\.docx$/i, '').trim()
    }
  }

  function selectNode(id: string | null): void {
    selectedId.value = id
  }

  function moveSelected(dir: -1 | 1): void {
    if (!selectedId.value) return
    tree.value = moveNode(tree.value, selectedId.value, dir)
  }

  function deleteSelected(): void {
    if (!selectedId.value) return
    tree.value = deleteNode(tree.value, selectedId.value)
    selectedId.value = null
  }

  function promoteSelected(): void {
    if (!selectedId.value) return
    tree.value = promoteNode(tree.value, selectedId.value)
  }

  function demoteSelected(): void {
    if (!selectedId.value) return
    tree.value = demoteNode(tree.value, selectedId.value)
  }

  function addChild(parentId: string | null, type: ContentType): void {
    tree.value = addChildNode(tree.value, parentId, type)
  }

  function addSibling(siblingId: string, type: ContentType): void {
    tree.value = addSiblingNode(tree.value, siblingId, type)
  }

  function updateSelectedFields(patch: { title?: string; skip_numbering?: boolean; mark_status?: MarkStatus }): void {
    if (!selectedId.value) return
    tree.value = updateNode(tree.value, selectedId.value, patch)
  }

  // ---- 层级标定动作 ---- //
  // 标定走「重建」语义（见 importTree.applyLayerRole）：顺序无关、子树整体平移、
  // 不可达层级夹紧、绝不把章节嵌进正文、内容↔章节互转保数据。
  function applyLayerMarking(role: LayerRole): void {
    const ids = [...markSelection.value]
    if (ids.length === 0) return

    if (role === 'ignored') {
      const [next, removed] = extractIgnored(tree.value, ids)
      tree.value = next
      ignored.value = [...ignored.value, ...removed]
      exitMode()
      return
    }

    tree.value = applyLayerRole(tree.value, ids, role)
    exitMode()
  }

  // ---- 步骤标注动作 ---- //
  function applyStepAnnotation(role: 'step' | 'content'): void {
    const ids = [...markSelection.value]
    if (ids.length === 0) return
    tree.value = setMarkStatus(tree.value, ids, role)
    exitMode()
  }

  function clearStepAnnotation(): void {
    const ids = [...markSelection.value]
    if (ids.length === 0) return
    tree.value = setMarkStatus(tree.value, ids, 'unmarked')
    exitMode()
  }

  // ---- 忽略项恢复 ---- //
  function restoreIgnored(id: string): void {
    const idx = ignored.value.findIndex((n) => n.id === id)
    if (idx === -1) return
    const node = ignored.value[idx]
    ignored.value = ignored.value.filter((_, i) => i !== idx)
    tree.value = restoreFromIgnored(tree.value, [node])
  }

  function restoreAllIgnored(): void {
    if (ignored.value.length === 0) return
    tree.value = restoreFromIgnored(tree.value, ignored.value)
    ignored.value = []
  }

  // ---- 接受 review ---- //
  function acceptReview(id: string): void {
    tree.value = updateNode(tree.value, id, { mark_status: 'unmarked' })
  }

  return {
    // state
    file, uploadToken, filename, parseResult,
    tree, ignored, selectedId, mode, markSelection, form,
    // derived
    selected, levelMap, numberMap, reviewCount,
    // mode
    toggleLayerMarking, toggleStepAnnotation, exitMode,
    toggleMarkSelection, clearMarkSelection,
    // tree actions
    loadParseResult, selectNode, moveSelected, deleteSelected,
    promoteSelected, demoteSelected, addChild, addSibling, updateSelectedFields,
    // layer marking
    applyLayerMarking,
    // step annotation
    applyStepAnnotation, clearStepAnnotation,
    // ignored
    restoreIgnored, restoreAllIgnored,
    // review
    acceptReview,
  }
}
