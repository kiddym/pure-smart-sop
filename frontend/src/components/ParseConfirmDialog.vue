<script setup lang="ts">
import { computed } from 'vue'
import type { ParseWarning } from '@/types/parse'

defineOptions({ name: 'ParseConfirmDialog' })

const props = defineProps<{ modelValue: boolean; warnings: ParseWarning[] }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
const count = computed(() => props.warnings.length)
</script>

<template>
  <el-dialog v-model="visible" :title="`检测到 ${count} 项内容可能未提取`" width="480px">
    <p class="lead">以下内容可能未能成功解析、导入后将缺失。是否仍要继续导入？</p>
    <ul class="warn-list">
      <li v-for="(w, i) in warnings" :key="i">{{ w.message }}</li>
    </ul>
    <template #footer>
      <el-button @click="emit('cancel')">取消导入</el-button>
      <el-button type="warning" @click="emit('confirm')">仍要继续导入</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.lead { color: #606266; font-size: 13px; margin: 0 0 8px; }
.warn-list { margin: 0; padding-left: 18px; color: var(--el-color-danger, #f56c6c); font-size: 13px; }
.warn-list li { margin: 2px 0; }
</style>
