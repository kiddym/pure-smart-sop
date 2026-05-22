<script setup lang="ts">
import { computed } from 'vue'
import type { InputSchema } from '@/types/node'

// 执行表单 12 型动态配置（§4.1 执行记录区 / Q261-Q262）。
const props = defineProps<{ schema: InputSchema; readonly?: boolean }>()
const emit = defineEmits<{ (e: 'update:schema', value: InputSchema): void }>()

const type = computed(() => props.schema.type)

function set(key: string, value: unknown): void {
  emit('update:schema', { ...props.schema, [key]: value })
}
function str(key: string): string {
  const v = props.schema[key]
  return typeof v === 'string' ? v : ''
}
function num(key: string): number | undefined {
  const v = props.schema[key]
  return typeof v === 'number' ? v : undefined
}
const options = computed<string[]>(() => {
  const v = props.schema.options
  return Array.isArray(v) ? v.map((x) => String(x)) : []
})
function setOption(i: number, value: string): void {
  const list = [...options.value]
  list[i] = value
  set('options', list)
}
function addOption(): void {
  set('options', [...options.value, ''])
}
function removeOption(i: number): void {
  set(
    'options',
    options.value.filter((_, idx) => idx !== i),
  )
}
</script>

<template>
  <div class="form-fields">
    <template v-if="type === 'CHECK'">
      <el-form-item label="通过标签">
        <el-input :model-value="str('pass_label')" :disabled="readonly" @input="(v: string) => set('pass_label', v)" />
      </el-form-item>
      <el-form-item label="不通过标签">
        <el-input :model-value="str('fail_label')" :disabled="readonly" @input="(v: string) => set('fail_label', v)" />
      </el-form-item>
    </template>

    <template v-else-if="type === 'NUMBER'">
      <el-form-item label="单位">
        <el-input :model-value="str('unit')" :disabled="readonly" @input="(v: string) => set('unit', v)" />
      </el-form-item>
      <div class="num-row">
        <el-form-item label="最小值">
          <el-input-number :model-value="num('min')" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('min', v)" />
        </el-form-item>
        <el-form-item label="最大值">
          <el-input-number :model-value="num('max')" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('max', v)" />
        </el-form-item>
        <el-form-item label="小数位">
          <el-input-number :model-value="num('decimals')" :min="0" :max="6" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('decimals', v)" />
        </el-form-item>
      </div>
    </template>

    <template v-else-if="type === 'METER'">
      <el-form-item label="单位">
        <el-input :model-value="str('unit')" :disabled="readonly" @input="(v: string) => set('unit', v)" />
      </el-form-item>
    </template>

    <template v-else-if="type === 'CHECKBOX' || type === 'RADIO'">
      <el-form-item label="选项">
        <div class="opt-list">
          <div v-for="(opt, i) in options" :key="i" class="opt-row">
            <el-input :model-value="opt" :disabled="readonly" placeholder="选项文本" @input="(v: string) => setOption(i, v)" />
            <el-button v-if="!readonly" size="small" text @click="removeOption(i)">✕</el-button>
          </div>
          <el-button v-if="!readonly" size="small" @click="addOption">+ 添加选项</el-button>
        </div>
      </el-form-item>
    </template>

    <template v-else-if="type === 'UPLOAD'">
      <el-form-item label="接受类型 (accept)">
        <el-input :model-value="str('accept')" :disabled="readonly" placeholder="如 image/*,.pdf" @input="(v: string) => set('accept', v)" />
      </el-form-item>
      <el-form-item label="最大数量">
        <el-input-number :model-value="num('max_count')" :min="1" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('max_count', v)" />
      </el-form-item>
    </template>

    <el-text v-else type="info" size="small">该类型无需额外配置。</el-text>
  </div>
</template>

<style scoped>
.num-row {
  display: flex;
  gap: 12px;
}
.opt-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.opt-row {
  display: flex;
  gap: 6px;
  align-items: center;
}
</style>
