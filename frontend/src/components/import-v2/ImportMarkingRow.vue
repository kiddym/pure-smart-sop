<script setup lang="ts">
import type { LayerRole } from '@/utils/importTree'

defineProps<{
  label: string
  role: LayerRole
  indent: number
}>()
const emit = defineEmits<{ (e: 'set', role: LayerRole): void }>()

const OPTIONS: { value: LayerRole; text: string }[] = [
  { value: 'chapter_1', text: '一级' },
  { value: 'chapter_2', text: '二级' },
  { value: 'chapter_3', text: '三级' },
  { value: 'content', text: '正文' },
]

function onChange(v: string | number | boolean): void {
  emit('set', v as LayerRole)
}
</script>

<template>
  <div class="mr" :style="{ paddingLeft: `${indent * 16 + 8}px` }">
    <el-radio-group :model-value="role" size="small" class="mr-roles" @change="onChange">
      <el-radio-button v-for="o in OPTIONS" :key="o.value" :value="o.value">{{ o.text }}</el-radio-button>
    </el-radio-group>
    <span class="mr-title">{{ label }}</span>
  </div>
</template>

<style scoped>
.mr {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 4px 8px 4px 0; /* 左内边距由内联 paddingLeft（缩进）掌管 */
  border-bottom: 1px solid var(--el-border-color-lighter, #f0f0f0);
  font-size: 13px;
}
.mr:hover { background: #f5f7fa; }
.mr-roles { flex: none; }
.mr-title {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #303133;
}
</style>
