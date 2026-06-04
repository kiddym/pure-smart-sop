<script setup lang="ts">
import { onMounted } from 'vue'
import FolderTree from '@/components/FolderTree.vue'
import { useFolderStore } from '@/store/folders'
import type { FolderTreeNode } from '@/types/folder'

defineEmits<{
  (e: 'select', node: FolderTreeNode | null): void
}>()

const store = useFolderStore()

onMounted(() => {
  void store.loadTree()
})
</script>

<template>
  <div class="folder-tree-pane">
    <header class="pane-header">
      <span class="title">文件夹</span>
    </header>
    <div class="tree-body">
      <FolderTree
        :data="store.tree"
        :loading="store.loading"
        @select="(n) => $emit('select', n)"
      />
    </div>
  </div>
</template>

<style scoped>
.folder-tree-pane {
  width: 220px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.pane-header {
  height: 40px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
}
.pane-header .title {
  font-size: 12px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.tree-body {
  flex: 1;
  overflow: auto;
  padding: 8px 0;
}
</style>
