<script setup lang="ts">
import { computed, ref } from 'vue'
import RichTextEditor from './RichTextEditor.vue'
import StepFormFields from './StepFormFields.vue'
import FormFieldPreview from './FormFieldPreview.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { FORM_TYPE_META } from '@/utils/editor'
import { FORM_TYPES } from '@/types/node'
import type { AttachmentMark, FormType, InputSchema } from '@/types/node'

type AlertField = 'note' | 'caution' | 'warning'

// step 节点详情（§4.1，§40 重构）：基本信息 / 警示 / 正文 / 附件标记 / 执行记录 / 其他。
const store = useProcedureEditorStore()
const step = computed(() => store.selectedStep)
const ro = computed(() => !store.editable)
const active = ref(['basic', 'alerts', 'body', 'attach', 'exec', 'other'])

const ATTACH_KINDS = [
  { value: 'video', label: '视频' },
  { value: 'image', label: '图片' },
  { value: 'document', label: '文档' },
  { value: 'audio', label: '音频' },
  { value: 'other', label: '其他' },
]

function upd(patch: Record<string, unknown>, tag?: string): void {
  const id = step.value?.id
  if (id) store.updateStepFields(id, patch, tag)
}
function updMark(i: number, patch: Partial<AttachmentMark>): void {
  const s = step.value
  if (!s) return
  upd({ attachment_marks: s.attachment_marks.map((m, idx) => (idx === i ? { ...m, ...patch } : m)) })
}
function addMark(): void {
  const s = step.value
  if (!s) return
  upd({ attachment_marks: [...s.attachment_marks, { filename: '', kind: 'document', note: '' }] })
}
function removeMark(i: number): void {
  const s = step.value
  if (!s) return
  upd({ attachment_marks: s.attachment_marks.filter((_, idx) => idx !== i) })
}
function onSchema(schema: InputSchema): void {
  upd({ input_schema: schema })
}
function onAlertSchema(field: AlertField, schema: InputSchema): void {
  upd({ [`${field}_schema`]: schema })
}
function setAlertFormType(field: AlertField, type: FormType): void {
  upd({ [`${field}_schema`]: { type } as InputSchema })
}
</script>

<template>
  <div v-if="step" class="step-detail">
    <el-collapse v-model="active">
      <el-collapse-item title="基本信息" name="basic">
        <el-form label-position="top">
          <el-form-item label="步骤标题">
            <el-input
              :model-value="step.title"
              :disabled="ro"
              maxlength="500"
              placeholder="步骤标题（可空，发布时仅提示）"
              @input="(v: string) => upd({ title: v }, `title:${step!.id}`)"
            />
          </el-form-item>
          <div class="inline">
            <el-form-item label="执行表单类型">
              <el-select
                :model-value="step.input_schema.type"
                :disabled="ro"
                @change="(v: FormType) => store.setStepFormType(step!.id, v)"
              >
                <el-option v-for="t in FORM_TYPES" :key="t" :value="t" :label="FORM_TYPE_META[t].label" />
              </el-select>
            </el-form-item>
            <el-form-item label="跳号">
              <el-switch :model-value="step.skip_numbering" :disabled="ro" @change="store.toggleSkipNumbering(step!.id)" />
            </el-form-item>
          </div>
        </el-form>
      </el-collapse-item>

      <el-collapse-item title="警示（注意 / 小心 / 警告）" name="alerts">
        <div class="alert-block alert-note">
          <div class="alert-header">
            <span class="alert-label">注意 Note</span>
            <el-select
              :model-value="step.note_schema.type"
              :disabled="ro"
              size="small"
              class="alert-type-select"
              @change="(v: FormType) => setAlertFormType('note', v)"
            >
              <el-option v-for="t in FORM_TYPES" :key="t" :value="t" :label="FORM_TYPE_META[t].label" />
            </el-select>
          </div>
          <RichTextEditor v-if="step.note_schema.type === 'COMMON'" :key="`note-${step.id}`" :model-value="step.note" variant="step" :readonly="ro" @update:model-value="(v) => upd({ note: v }, `note:${step!.id}`)" />
          <el-form v-else label-position="top">
            <div class="config-preview">
              <div class="cp-config">
                <StepFormFields :schema="step.note_schema" :readonly="ro" @update:schema="(s) => onAlertSchema('note', s)" />
              </div>
              <div class="cp-preview">
                <FormFieldPreview :schema="step.note_schema" />
              </div>
            </div>
          </el-form>
        </div>
        <div class="alert-block alert-caution">
          <div class="alert-header">
            <span class="alert-label">小心 Caution</span>
            <el-select
              :model-value="step.caution_schema.type"
              :disabled="ro"
              size="small"
              class="alert-type-select"
              @change="(v: FormType) => setAlertFormType('caution', v)"
            >
              <el-option v-for="t in FORM_TYPES" :key="t" :value="t" :label="FORM_TYPE_META[t].label" />
            </el-select>
          </div>
          <RichTextEditor v-if="step.caution_schema.type === 'COMMON'" :key="`caution-${step.id}`" :model-value="step.caution" variant="step" :readonly="ro" @update:model-value="(v) => upd({ caution: v }, `caution:${step!.id}`)" />
          <el-form v-else label-position="top">
            <div class="config-preview">
              <div class="cp-config">
                <StepFormFields :schema="step.caution_schema" :readonly="ro" @update:schema="(s) => onAlertSchema('caution', s)" />
              </div>
              <div class="cp-preview">
                <FormFieldPreview :schema="step.caution_schema" />
              </div>
            </div>
          </el-form>
        </div>
        <div class="alert-block alert-warning">
          <div class="alert-header">
            <span class="alert-label">警告 Warning</span>
            <el-select
              :model-value="step.warning_schema.type"
              :disabled="ro"
              size="small"
              class="alert-type-select"
              @change="(v: FormType) => setAlertFormType('warning', v)"
            >
              <el-option v-for="t in FORM_TYPES" :key="t" :value="t" :label="FORM_TYPE_META[t].label" />
            </el-select>
          </div>
          <RichTextEditor v-if="step.warning_schema.type === 'COMMON'" :key="`warning-${step.id}`" :model-value="step.warning" variant="step" :readonly="ro" @update:model-value="(v) => upd({ warning: v }, `warning:${step!.id}`)" />
          <el-form v-else label-position="top">
            <div class="config-preview">
              <div class="cp-config">
                <StepFormFields :schema="step.warning_schema" :readonly="ro" @update:schema="(s) => onAlertSchema('warning', s)" />
              </div>
              <div class="cp-preview">
                <FormFieldPreview :schema="step.warning_schema" />
              </div>
            </div>
          </el-form>
        </div>
      </el-collapse-item>

      <el-collapse-item title="正文" name="body">
        <RichTextEditor :key="`body-${step.id}`" :model-value="step.content" variant="step" :readonly="ro" placeholder="操作说明正文…" @update:model-value="(v) => upd({ content: v }, `content:${step!.id}`)" />
      </el-collapse-item>

      <el-collapse-item title="附件标记" name="attach">
        <div v-for="(m, i) in step.attachment_marks" :key="i" class="mark-row">
          <el-input :model-value="m.filename" :disabled="ro" placeholder="文件名" @input="(v: string) => updMark(i, { filename: v })" />
          <el-select :model-value="m.kind" :disabled="ro" class="mark-kind" @change="(v: string) => updMark(i, { kind: v })">
            <el-option v-for="k in ATTACH_KINDS" :key="k.value" :value="k.value" :label="k.label" />
          </el-select>
          <el-input :model-value="m.note" :disabled="ro" placeholder="备注" @input="(v: string) => updMark(i, { note: v })" />
          <el-button v-if="!ro" size="small" text @click="removeMark(i)">✕</el-button>
        </div>
        <el-button v-if="!ro" size="small" @click="addMark">+ 附件标记</el-button>
      </el-collapse-item>

      <el-collapse-item title="执行记录" name="exec">
        <el-form label-position="top">
          <div class="config-preview">
            <div class="cp-config">
              <StepFormFields :schema="step.input_schema" :readonly="ro" @update:schema="onSchema" />
            </div>
            <div class="cp-preview">
              <FormFieldPreview :schema="step.input_schema" />
            </div>
          </div>
          <el-checkbox :model-value="step.require_confirmation" :disabled="ro" @change="(v: string | number | boolean) => upd({ require_confirmation: !!v })">
            需要操作员确认
          </el-checkbox>
        </el-form>
      </el-collapse-item>

      <el-collapse-item title="其他" name="other">
        <el-form label-position="top">
          <el-form-item label="预期输出">
            <el-input :model-value="step.expected_output" type="textarea" :rows="2" maxlength="10000" :disabled="ro" @input="(v: string) => upd({ expected_output: v }, `exp:${step!.id}`)" />
          </el-form-item>
        </el-form>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<style scoped>
.inline {
  display: flex;
  gap: 16px;
}
.config-preview {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.cp-config,
.cp-preview {
  flex: 1 1 280px;
  min-width: 0;
}
.alert-block {
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid transparent;
}
.alert-note {
  border-left-color: #409eff;
}
.alert-caution {
  border-left-color: #e6a23c;
}
.alert-warning {
  border-left-color: #f56c6c;
}
.alert-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.alert-label {
  font-size: 12px;
  color: #909399;
  flex: none;
}
.alert-type-select {
  width: 160px;
}
.mark-row {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-bottom: 6px;
}
.mark-kind {
  width: 120px;
  flex: none;
}
</style>
