<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchFolderTree } from '@/api/folders'
import { collectLeafFolders, type LeafFolderOption } from '@/utils/folders'

// 版本动作统一弹框（Q356）：按需渲染 reason / 目标文件夹 / 名称 字段，覆盖 rollback / deprecate / restore / copy。
export interface VersionActionResult {
  reason: string
  target_folder_id: string
  name: string
}

const props = defineProps<{
  modelValue: boolean
  title: string
  needReason: boolean
  needFolder: boolean
  needName: boolean
  reasonHint?: string
  loading?: boolean
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'confirm', payload: VersionActionResult): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const reason = ref('')
const folderId = ref('')
const name = ref('')
const leaves = ref<LeafFolderOption[]>([])
const loadingLeaves = ref(false)

watch(visible, async (open) => {
  if (!open) return
  reason.value = ''
  folderId.value = ''
  name.value = ''
  if (props.needFolder && !leaves.value.length) {
    loadingLeaves.value = true
    try {
      leaves.value = collectLeafFolders(await fetchFolderTree())
    } finally {
      loadingLeaves.value = false
    }
  }
})

function confirm(): void {
  if (props.needReason && !reason.value.trim()) {
    ElMessage.warning('请填写原因')
    return
  }
  if (props.needFolder && !folderId.value) {
    ElMessage.warning('请选择目标文件夹')
    return
  }
  emit('confirm', {
    reason: reason.value.trim(),
    target_folder_id: folderId.value,
    name: name.value.trim(),
  })
}
</script>

<template>
  <el-dialog v-model="visible" :title="title" width="480px">
    <el-form label-position="top">
      <el-form-item v-if="needName" label="新程序名称（留空=源名 + 副本）">
        <el-input v-model="name" maxlength="200" placeholder="新程序名称" />
      </el-form-item>
      <el-form-item v-if="needFolder" label="目标文件夹" required>
        <el-select
          v-model="folderId"
          filterable
          :loading="loadingLeaves"
          placeholder="仅可存程序的叶子文件夹"
          class="full"
        >
          <el-option v-for="leaf in leaves" :key="leaf.id" :label="leaf.label" :value="leaf.id" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="needReason" label="原因" required>
        <el-input
          v-model="reason"
          type="textarea"
          :rows="3"
          maxlength="2000"
          :placeholder="reasonHint || '请填写原因（将记入版本变更日志）'"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="confirm">确定</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.full {
  width: 100%;
}
</style>
