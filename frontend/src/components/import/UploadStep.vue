<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadRawFile } from 'element-plus'
import { formatBytes, uploadSizeTier } from '@/utils/upload'

// step1：拖拽上传 + .docx 校验 + 三档体积预警（Q352）。仅选取 File 上抛，真正上传在向导「下一步」触发。
const props = defineProps<{ file: File | null; filename: string }>()
const emit = defineEmits<{
  (e: 'select', file: File): void
  (e: 'clear'): void
}>()

const tier = computed(() => (props.file ? uploadSizeTier(props.file.size) : null))
const ALERT_TYPE = { ok: 'success', info: 'info', warning: 'warning', error: 'error' } as const

function pick(raw: UploadRawFile): boolean {
  if (!raw.name.toLowerCase().endsWith('.docx')) {
    ElMessage.error('仅支持 .docx 格式（Word 文档）')
    return false
  }
  if (uploadSizeTier(raw.size).tier === 'error') {
    ElMessage.error(`文件超过 50MB 上限，无法上传`)
    return false
  }
  emit('select', raw)
  return false // 阻止 el-upload 自动上传（auto-upload=false 亦不会上传，这里双保险）
}
</script>

<template>
  <div class="upload-step">
    <el-upload
      drag
      action="#"
      :auto-upload="false"
      :show-file-list="false"
      :limit="1"
      accept=".docx"
      :before-upload="pick"
    >
      <div class="drop">
        <el-icon class="ico"><svg viewBox="0 0 1024 1024" width="48" height="48"><path fill="currentColor" d="M544 864V672h128L512 480 352 672h128v192H320v-1.6c-5.376.32-10.496 1.6-16 1.6A240 240 0 0 1 64 624c0-123.136 93.12-223.488 212.608-237.248A256.256 256.256 0 0 1 512 224a256.256 256.256 0 0 1 235.392 162.752C866.88 400.512 960 500.864 960 624a240 240 0 0 1-240 240c-5.504 0-10.624-1.28-16-1.6V864z"/></svg></el-icon>
        <div class="hint">将 Word 文档（.docx）拖到此处，或<em>点击选择</em></div>
        <div class="sub">单文件最大 50MB；仅支持 .docx</div>
      </div>
    </el-upload>

    <div v-if="file" class="selected">
      <div class="row">
        <span class="fname">{{ filename }}</span>
        <span class="fsize">{{ formatBytes(file.size) }}</span>
        <el-button text type="danger" size="small" @click="emit('clear')">移除</el-button>
      </div>
      <el-alert
        v-if="tier && tier.tier !== 'ok'"
        :type="ALERT_TYPE[tier.tier]"
        :title="tier.message"
        :closable="false"
        show-icon
        class="size-alert"
      />
    </div>
  </div>
</template>

<style scoped>
.upload-step {
  padding: 8px 0;
}
.drop {
  padding: 24px 0;
}
.ico {
  color: var(--el-color-primary, #409eff);
  margin-bottom: 8px;
}
.hint {
  color: #606266;
}
.hint em {
  color: var(--el-color-primary, #409eff);
  font-style: normal;
}
.sub {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
}
.selected {
  margin-top: 16px;
}
.row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.fname {
  font-weight: 600;
}
.fsize {
  color: #909399;
  font-size: 12px;
}
.size-alert {
  margin-top: 10px;
}
</style>
