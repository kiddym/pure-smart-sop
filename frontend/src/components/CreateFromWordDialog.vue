<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchFolderTree } from '@/api/folders'
import { uploadAndParse, importParsed, type ImportStage } from '@/api/parse'
import type { FolderTreeNode } from '@/types/folder'
import type { ParseResponse, ParseWarning } from '@/types/parse'
import ParseConfirmDialog from '@/components/ParseConfirmDialog.vue'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'imported', id: string): void
}>()
const visible = computed({ get: () => props.modelValue, set: (v) => emit('update:modelValue', v) })

interface LeafOption { id: string; label: string }
const leaves = ref<LeafOption[]>([])
const file = ref<File | null>(null)
const form = reactive({ folder_id: '', name: '' })
const stage = ref<ImportStage | ''>('')
const uploadPct = ref(0)
const errorMsg = ref('')
const parsed = ref<ParseResponse | null>(null)
const uploadToken = ref('')
const confirmVisible = ref(false)
const blockingWarnings = ref<ParseWarning[]>([])
const busy = computed(() => stage.value !== '')
const stageLabel = computed(() => {
  if (stage.value === 'uploading') return `上传中… ${uploadPct.value}%`
  if (stage.value === 'parsing') return '解析中…'
  if (stage.value === 'creating') return '创建中…'
  return ''
})

function errorMessage(e: unknown): string {
  const detail = (e as { response?: { data?: { detail?: { message?: string } } } })?.response?.data
    ?.detail
  return detail?.message ?? '导入失败，请检查文件后重试'
}

function collectLeaves(nodes: FolderTreeNode[], acc: LeafOption[]): void {
  for (const n of nodes) {
    if (!n.system && n.children.length === 0 && n.prefix) acc.push({ id: n.id, label: n.full_path })
    if (n.children.length) collectLeaves(n.children, acc)
  }
}
async function loadLeaves(): Promise<void> {
  const acc: LeafOption[] = []
  collectLeaves(await fetchFolderTree(), acc)
  leaves.value = acc
}
watch(visible, (open) => {
  if (open) {
    file.value = null
    form.folder_id = ''
    form.name = ''
    stage.value = ''
    uploadPct.value = 0
    errorMsg.value = ''
    void loadLeaves()
  }
})
function onFile(e: Event): void {
  const f = (e.target as HTMLInputElement).files?.[0] ?? null
  file.value = f
  if (f && !form.name.trim()) form.name = f.name.replace(/\.docx$/i, '')
}
async function submit(): Promise<void> {
  if (!file.value) { ElMessage.warning('请选择 .docx 文件'); return }
  if (!form.folder_id) { ElMessage.warning('请选择目标文件夹'); return }
  if (!form.name.trim()) { ElMessage.warning('请输入程序名称'); return }
  errorMsg.value = ''
  try {
    const r = await uploadAndParse(file.value, (s, pct) => {
      stage.value = s
      if (pct !== undefined) uploadPct.value = pct
    })
    parsed.value = r.parsed
    uploadToken.value = r.uploadToken
    const blocking = r.parsed.warnings.filter((w) => w.severity === 'blocking')
    if (blocking.length) {
      blockingWarnings.value = blocking
      confirmVisible.value = true
      stage.value = ''
      uploadPct.value = 0
      return
    }
    await doImport()
  } catch (e) {
    errorMsg.value = errorMessage(e)
    stage.value = ''
    uploadPct.value = 0
  }
}

async function doImport(): Promise<void> {
  if (!parsed.value) return
  try {
    stage.value = 'creating'
    const proc = await importParsed({
      uploadToken: uploadToken.value,
      folderId: form.folder_id,
      name: form.name.trim(),
      chapters: parsed.value.chapters,
      importNotes: parsed.value.warnings,
    })
    ElMessage.success(`已创建 ${proc.code}`)
    visible.value = false
    emit('imported', proc.id)
  } catch (e) {
    errorMsg.value = errorMessage(e)
  } finally {
    stage.value = ''
    uploadPct.value = 0
  }
}

function onConfirmContinue(): void {
  confirmVisible.value = false
  void doImport()
}
function onCancelImport(): void {
  confirmVisible.value = false
  stage.value = ''
  uploadPct.value = 0
}
</script>

<template>
  <el-dialog v-model="visible" title="从 Word 导入" width="520px">
    <el-form label-width="96px">
      <el-form-item label="Word 文件" required>
        <input type="file" accept=".docx" @change="onFile" />
      </el-form-item>
      <el-form-item label="目标文件夹" required>
        <el-select v-model="form.folder_id" filterable placeholder="仅可存程序的叶子文件夹" class="full">
          <el-option v-for="l in leaves" :key="l.id" :label="l.label" :value="l.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="程序名称" required>
        <el-input v-model="form.name" maxlength="200" placeholder="默认取文件名" />
      </el-form-item>
      <div v-if="busy" class="phase">{{ stageLabel }}</div>
      <div v-if="errorMsg" class="err">{{ errorMsg }}</div>
    </el-form>
    <template #footer>
      <el-button :disabled="busy" @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="busy" @click="submit">导入并编辑</el-button>
    </template>
  </el-dialog>
  <ParseConfirmDialog
    v-model="confirmVisible"
    :warnings="blockingWarnings"
    @confirm="onConfirmContinue"
    @cancel="onCancelImport"
  />
</template>

<style scoped>
.full { width: 100%; }
.phase { color: #606266; font-size: 13px; padding-left: 96px; }
.err { color: var(--el-color-danger, #f56c6c); font-size: 13px; padding-left: 96px; }
</style>
