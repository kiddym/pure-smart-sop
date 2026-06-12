<script setup lang="ts">
import { computed } from 'vue'
import type { FieldOption, FieldType } from '@/types/field'

// 自定义字段单控件（从 ProcedureDetailsPanel 抽出）：按 field_type 渲染输入控件或只读文本。
interface FieldDef {
  field_type: FieldType
  options: FieldOption[]
}
const props = defineProps<{ field: FieldDef; modelValue: unknown; readonly?: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: unknown): void }>()

const str = computed(() =>
  props.modelValue === undefined || props.modelValue === null ? '' : String(props.modelValue),
)
const arr = computed<string[]>(() =>
  Array.isArray(props.modelValue) ? (props.modelValue as string[]) : [],
)
const opts = computed(() => props.field.options.map((o) => ({ value: o.value, label: o.label })))

const readonlyText = computed(() => {
  const t = props.field.field_type
  if (t === 'select') return opts.value.find((o) => o.value === str.value)?.label ?? str.value
  if (t === 'multi_select' || t === 'checkbox')
    return arr.value.map((v) => opts.value.find((o) => o.value === v)?.label ?? v).join(', ')
  return str.value
})

function set(v: unknown): void {
  emit('update:modelValue', v)
}
</script>

<template>
  <!-- read-only: plain text display -->
  <span v-if="props.readonly" class="custom-readonly">{{ readonlyText }}</span>

  <!-- textarea -->
  <el-input
    v-else-if="field.field_type === 'textarea'"
    :model-value="str"
    type="textarea"
    :rows="3"
    @input="(v: string) => set(v)"
  />

  <!-- number -->
  <el-input-number
    v-else-if="field.field_type === 'number'"
    :model-value="str === '' ? undefined : Number(str)"
    @change="(v: number | undefined) => set(v)"
  />

  <!-- date -->
  <el-date-picker
    v-else-if="field.field_type === 'date'"
    :model-value="str"
    type="date"
    value-format="YYYY-MM-DD"
    @update:model-value="(v: string | null) => set(v ?? '')"
  />

  <!-- select -->
  <el-select
    v-else-if="field.field_type === 'select'"
    :model-value="str"
    @update:model-value="(v: string) => set(v)"
  >
    <el-option v-for="opt in opts" :key="opt.value" :value="opt.value" :label="opt.label" />
  </el-select>

  <!-- multi_select -->
  <el-select
    v-else-if="field.field_type === 'multi_select'"
    :model-value="arr"
    multiple
    @update:model-value="(v: string[]) => set(v)"
  >
    <el-option v-for="opt in opts" :key="opt.value" :value="opt.value" :label="opt.label" />
  </el-select>

  <!-- checkbox: single option → el-switch; multiple options → el-checkbox-group -->
  <el-switch
    v-else-if="field.field_type === 'checkbox' && opts.length <= 1"
    :model-value="Boolean(modelValue)"
    @update:model-value="(v: boolean) => set(v)"
  />
  <el-checkbox-group
    v-else-if="field.field_type === 'checkbox'"
    :model-value="arr"
    @update:model-value="(v: string[]) => set(v)"
  >
    <el-checkbox v-for="opt in opts" :key="opt.value" :value="opt.value" :label="opt.label" />
  </el-checkbox-group>

  <!-- text + fallback: plain text input -->
  <el-input v-else :model-value="str" type="text" @input="(v: string) => set(v)" />
</template>

<style scoped>
.custom-readonly {
  color: var(--el-text-color-regular);
  word-break: break-word;
}
</style>
