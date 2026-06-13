<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { listFields } from '@/api/fields'
import { collectDeprecatedFieldValues } from '@/utils/editor'
import { LEVEL_OF_USE_LABELS } from '@/utils/format'
import CustomFieldInput from './CustomFieldInput.vue'
import ReferencePanel from './ReferencePanel.vue'
import type { LevelOfUse } from '@/types/procedure'
import type { FieldDetailOut } from '@/types/field'

// 程序详情（§1.2 / Q162）：元字段 + 自定义字段。作为右栏「程序详情」tab 内容直接平铺。
const store = useProcedureEditorStore()
const p = computed(() => store.procedure)
const ro = computed(() => !store.editable)

// 已废弃字段（归档/删除后历史值不丢，只读展示，Q255/Q256）：拉归档字段定义贴标签，失败则回退 key。
const archivedFields = ref<FieldDetailOut[]>([])
onMounted(async () => {
  try {
    archivedFields.value = await listFields({ status: 'archived' })
  } catch {
    archivedFields.value = []
  }
})
const deprecatedEntries = computed(() =>
  collectDeprecatedFieldValues(
    p.value?.custom_values ?? {},
    store.fields.map((f) => f.key),
    archivedFields.value,
  ),
)

function setCustom(key: string, value: unknown): void {
  if (!p.value) return
  store.setMetaField('custom_values', { ...p.value.custom_values, [key]: value })
}
function customVal(key: string): unknown {
  return p.value?.custom_values?.[key] ?? null
}
</script>

<template>
  <div v-if="p" class="details">
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

      <el-form-item label="PDF 签字栏">
        <el-switch
          :model-value="p.signoff_enabled"
          :disabled="ro"
          @change="(v: string | number | boolean) => store.setMetaField('signoff_enabled', !!v)"
        />
      </el-form-item>

      <template v-if="store.fields.length">
        <el-divider content-position="left">自定义字段</el-divider>
        <el-form-item v-for="f in store.fields" :key="f.id" :label="f.name" :required="f.required">
          <CustomFieldInput
            :field="f"
            :model-value="customVal(f.key)"
            :readonly="ro"
            @update:model-value="(v: unknown) => setCustom(f.key, v)"
          />
        </el-form-item>
      </template>
    </el-form>

    <el-collapse v-if="deprecatedEntries.length">
      <el-collapse-item name="deprecated">
        <template #title>
          <span class="deprecated-title">已废弃字段（{{ deprecatedEntries.length }}）</span>
        </template>
        <el-form label-width="110px" label-position="left">
          <el-form-item v-for="e in deprecatedEntries" :key="e.key" :label="e.label">
            <span class="custom-readonly">{{ e.value }}</span>
          </el-form-item>
        </el-form>
      </el-collapse-item>
    </el-collapse>

    <el-divider />
    <div class="ref-section">
      <div class="ref-title">参考关系</div>
      <ReferencePanel
        v-if="p"
        :procedure-id="p.id"
        :source-group-id="p.procedure_group_id"
        :readonly="ro"
      />
    </div>
  </div>
</template>

<style scoped>
.row2 {
  display: flex;
  gap: 16px;
}
.custom-readonly {
  color: var(--el-text-color-regular);
  word-break: break-word;
}
.deprecated-title {
  color: var(--el-text-color-secondary);
}
.ref-section { margin-top: 8px; }
.ref-title { font-weight: 600; font-size: 13px; margin-bottom: 6px; }
</style>
