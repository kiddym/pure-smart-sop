<script setup lang="ts">
import { computed } from 'vue'
import RichTextEditor from './RichTextEditor.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

// content 节点详情（§4.1）：仅富文本，无标题。
const store = useProcedureEditorStore()
const content = computed(() => store.selectedChapter)
const ro = computed(() => !store.editable)

function onChange(value: string): void {
  const id = content.value?.id
  if (id) store.updateChapterFields(id, { rich_content: value }, `rich:${id}`)
}
</script>

<template>
  <div v-if="content" class="content-detail">
    <RichTextEditor
      :key="`${content.id}:${ro}`"
      :model-value="content.rich_content"
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
