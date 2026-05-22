<script setup lang="ts">
import { computed } from 'vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { LEVEL_OF_USE_LABELS } from '@/utils/format'
import type { LevelOfUse } from '@/types/procedure'

// 程序详情折叠面板（§1.2 / Q162）：元字段 + 自定义字段，折叠收纳。
const store = useProcedureEditorStore()
const p = computed(() => store.procedure)
const ro = computed(() => !store.editable)

function setCustom(key: string, value: unknown): void {
  if (!p.value) return
  store.setMetaField('custom_values', { ...p.value.custom_values, [key]: value })
}
function customVal(key: string): string {
  const v = p.value?.custom_values?.[key]
  return v === undefined || v === null ? '' : String(v)
}
</script>

<template>
  <el-collapse v-if="p" class="details">
    <el-collapse-item title="程序详情 / 自定义字段" name="meta">
      <el-form label-width="110px" label-position="left">
        <el-form-item label="名称">
          <el-input :model-value="p.name" :disabled="ro" maxlength="200" @input="(v: string) => store.setMetaField('name', v)" />
        </el-form-item>
        <el-form-item label="用途级别">
          <el-select :model-value="p.level_of_use" :disabled="ro" @change="(v: LevelOfUse) => store.setMetaField('level_of_use', v)">
            <el-option v-for="(label, val) in LEVEL_OF_USE_LABELS" :key="val" :value="val" :label="label" />
          </el-select>
        </el-form-item>
        <div class="row2">
          <el-form-item label="风险等级">
            <el-input-number :model-value="p.risk_level" :min="1" :max="5" :disabled="ro" @change="(v: number | undefined) => store.setMetaField('risk_level', v ?? 1)" />
          </el-form-item>
          <el-form-item label="质量等级">
            <el-input-number :model-value="p.quality_level" :min="1" :max="5" :disabled="ro" @change="(v: number | undefined) => store.setMetaField('quality_level', v ?? 1)" />
          </el-form-item>
        </div>
        <el-form-item label="描述">
          <el-input :model-value="p.description" type="textarea" :rows="2" maxlength="10000" :disabled="ro" @input="(v: string) => store.setMetaField('description', v)" />
        </el-form-item>
        <el-form-item v-if="p.version > 1" label="版本更新说明">
          <el-input :model-value="p.version_update_notes" type="textarea" :rows="2" maxlength="10000" :disabled="ro" @input="(v: string) => store.setMetaField('version_update_notes', v)" />
        </el-form-item>

        <template v-if="store.fields.length">
          <el-divider content-position="left">自定义字段</el-divider>
          <el-form-item v-for="f in store.fields" :key="f.id" :label="f.name" :required="f.required">
            <el-input :model-value="customVal(f.key)" :disabled="ro" @input="(v: string) => setCustom(f.key, v)" />
          </el-form-item>
        </template>
      </el-form>
    </el-collapse-item>
  </el-collapse>
</template>

<style scoped>
.details {
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.row2 {
  display: flex;
  gap: 16px;
}
</style>
