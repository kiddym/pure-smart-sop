<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadFiles } from 'element-plus'

import { uploadDocx } from '@/api/parse'
import { createBatchImport } from '@/api/batchImports'

const props = defineProps<{ modelValue: boolean; folderId: string }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const router = useRouter()
const files = ref<File[]>([])
const parseMode = ref<'standard' | 'smart'>('smart')
const busy = ref(false)
const progress = ref(0)
// 文件项的内联错误（对齐 CreateFromWordDialog 的必填校验体验）。
const fileError = ref('')

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

// 关→开重置，避免上次选择残留。
watch(visible, (open) => {
  if (open) {
    files.value = []
    fileError.value = ''
    progress.value = 0
  }
})

// el-upload（手动上传）：每次变更同步整个文件列表，仅保留 .docx。
function onFilesChange(_file: UploadFile, fileList: UploadFiles): void {
  const picked: File[] = []
  for (const f of fileList) {
    if (f.raw && f.raw.name.toLowerCase().endsWith('.docx')) picked.push(f.raw)
  }
  files.value = picked
  if (files.value.length) fileError.value = ''
}

async function submit(): Promise<void> {
  if (!files.value.length) {
    fileError.value = '请至少选择一个 .docx 文件'
    return
  }
  fileError.value = ''
  busy.value = true
  progress.value = 0
  try {
    const items: { filename: string; upload_token: string }[] = []
    for (const file of files.value) {
      const up = await uploadDocx(file)
      items.push({ filename: file.name, upload_token: up.upload_token })
      progress.value = Math.round((items.length / files.value.length) * 100)
    }
    const job = await createBatchImport({
      folder_id: props.folderId, parse_mode: parseMode.value, items,
    })
    visible.value = false
    await router.push({ name: 'batch-review', params: { jobId: job.id } })
  } catch {
    ElMessage.error('批量上传失败，请重试')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="批量从 Word 导入" width="520px">
    <el-form label-width="96px">
      <el-form-item label="Word 文件" required :error="fileError">
        <el-upload
          class="uploader"
          accept=".docx"
          multiple
          :auto-upload="false"
          :show-file-list="true"
          :on-change="onFilesChange"
        >
          <el-button>选择 .docx 文件</el-button>
          <template #tip>
            <div class="hint">已选 {{ files.length }} 个文件</div>
          </template>
        </el-upload>
      </el-form-item>
      <el-form-item label="解析模式">
        <el-select v-model="parseMode">
          <el-option label="智能模式" value="smart" />
          <el-option label="标准模式" value="standard" />
        </el-select>
      </el-form-item>
      <el-progress v-if="busy" :percentage="progress" />
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="busy" @click="submit">上传并解析</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint {
  color: var(--text-secondary);
  font-size: 12px;
  margin-top: 4px;
}
</style>
