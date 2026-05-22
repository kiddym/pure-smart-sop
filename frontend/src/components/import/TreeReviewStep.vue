<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import ImportTreeNode from './ImportTreeNode.vue'
import {
  cloneTree,
  countReview,
  deleteNode,
  findNode,
  moveNode,
  updateNode,
  type WizardNode,
} from '@/utils/importTree'

// step4：树审查（中量编辑 title / skip / 删除 / 上下移）+ review 黄标 + 重置为初始解析（Q354）。
const props = defineProps<{ modelValue: WizardNode[]; initial: WizardNode[] }>()
const emit = defineEmits<{ (e: 'update:modelValue', tree: WizardNode[]): void }>()

const selectedId = ref<string | null>(null)
const selected = computed(() => (selectedId.value ? findNode(props.modelValue, selectedId.value) : null))
const reviewCount = computed(() => countReview(props.modelValue))

function commit(tree: WizardNode[]): void {
  emit('update:modelValue', tree)
}

const titleModel = computed<string>({
  get: () => selected.value?.title ?? '',
  set: (v) => {
    if (selectedId.value) commit(updateNode(props.modelValue, selectedId.value, { title: v }))
  },
})
const skipModel = computed<boolean>({
  get: () => selected.value?.skip_numbering ?? false,
  set: (v) => {
    if (selectedId.value) commit(updateNode(props.modelValue, selectedId.value, { skip_numbering: v }))
  },
})

function onDelete(id: string): void {
  void ElMessageBox.confirm('删除该节点及其全部子节点？此操作仅影响导入草稿。', '删除确认', {
    type: 'warning',
  }).then(() => {
    commit(deleteNode(props.modelValue, id))
    if (selectedId.value === id) selectedId.value = null
  })
}

function onMove(id: string, dir: -1 | 1): void {
  commit(moveNode(props.modelValue, id, dir))
}

function acceptSelectedReview(): void {
  if (selectedId.value) commit(updateNode(props.modelValue, selectedId.value, { mark_status: 'unmarked' }))
}

function resetTree(): void {
  void ElMessageBox.confirm('放弃当前所有调整，恢复为初始解析结果？', '重置确认', {
    type: 'warning',
  }).then(() => {
    selectedId.value = null
    commit(cloneTree(props.initial))
  })
}
</script>

<template>
  <div class="tree-step">
    <div class="bar">
      <span class="hint">共 {{ modelValue.length }} 个顶层章节</span>
      <span class="spacer" />
      <el-button size="small" @click="resetTree">重置为初始解析</el-button>
    </div>

    <el-alert
      v-if="reviewCount > 0"
      type="warning"
      :closable="false"
      show-icon
      class="banner"
      :title="`${reviewCount} 个低置信度节点需确认（黄色高亮）；继续下一步并提交即视为接受全部。`"
    />

    <div class="panes">
      <div class="tree">
        <ImportTreeNode
          v-for="node in modelValue"
          :key="node.id"
          :node="node"
          :depth="0"
          :selected-id="selectedId"
          @select="(id) => (selectedId = id)"
          @delete="onDelete"
          @move="onMove"
        />
        <el-empty v-if="!modelValue.length" description="树为空（已全部删除）" />
      </div>

      <div class="editor">
        <template v-if="selected">
          <el-form label-position="top">
            <el-form-item label="标题">
              <el-input v-model="titleModel" maxlength="500" placeholder="节点标题" />
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="skipModel">本节不参与自动编号（skip）</el-checkbox>
            </el-form-item>
            <el-form-item v-if="selected.mark_status === 'review'">
              <el-button size="small" type="warning" plain @click="acceptSelectedReview">
                接受此节点（清除待确认）
              </el-button>
            </el-form-item>
            <el-form-item v-if="selected.content_type === 'content' && selected.rich_content" label="内容预览">
              <!-- eslint-disable-next-line vue/no-v-html -->
              <div class="preview" v-html="selected.rich_content" />
            </el-form-item>
          </el-form>
        </template>
        <el-empty v-else description="选择左侧节点进行编辑" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.tree-step {
  padding: 8px 0;
}
.bar {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}
.hint {
  color: #909399;
  font-size: 13px;
}
.spacer {
  flex: 1;
}
.banner {
  margin-bottom: 12px;
}
.panes {
  display: flex;
  gap: 16px;
  min-height: 320px;
}
.tree {
  width: 50%;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  overflow: auto;
  max-height: 460px;
}
.editor {
  flex: 1;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  padding: 12px 16px;
}
.preview {
  width: 100%;
  border: 1px dashed var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  padding: 8px 12px;
  max-height: 240px;
  overflow: auto;
  font-size: 13px;
}
.preview :deep(img) {
  max-width: 100%;
}
</style>
