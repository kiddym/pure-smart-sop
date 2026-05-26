<script setup lang="ts">
import { computed } from 'vue'
import RichTextEditor from './RichTextEditor.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

// 内容块详情：内容块=kind='content' 的步骤，仅富文本（无标题/表单/附件/review）。
const store = useProcedureEditorStore()
const content = computed(() => store.selectedStep)
const ro = computed(() => !store.editable)

function onChange(value: string): void {
  const id = content.value?.id
  if (id) store.updateStepFields(id, { content: value }, `content:${id}`)
}
</script>

<template>
  <div v-if="content" class="content-detail">
    <RichTextEditor
      :key="`${content.id}:${ro}`"
      :model-value="content.content"
      variant="full"
      :readonly="ro"
      :procedure-id="store.procedure?.id"
      placeholder="输入内容块正文…"
      @update:model-value="onChange"
    />
  </div>
</template>

<style scoped>
.content-detail {
  height: 100%;
}
</style>
