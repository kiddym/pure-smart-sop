<script setup lang="ts">
import type { FolderTreeNode } from '@/types/folder'

defineProps<{ data: FolderTreeNode[]; loading?: boolean }>()
const emit = defineEmits<{ (e: 'select', node: FolderTreeNode): void }>()

const treeProps = { children: 'children', label: 'name' }
</script>

<template>
  <el-tree
    v-loading="loading"
    :data="data"
    :props="treeProps"
    node-key="id"
    highlight-current
    :expand-on-click-node="false"
    default-expand-all
    @node-click="(node: FolderTreeNode) => emit('select', node)"
  >
    <template #default="{ data: node }">
      <span class="ft-node">
        <span class="ft-name">{{ node.name }}</span>
        <el-tag v-if="node.system" size="small" type="info" class="ft-tag">系统</el-tag>
        <el-tag v-if="node.prefix" size="small" class="ft-tag">{{ node.prefix }}</el-tag>
        <span v-if="node.procedure_count" class="ft-count">{{ node.procedure_count }} 个程序</span>
      </span>
    </template>
  </el-tree>
</template>

<style scoped>
.ft-node {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.ft-count {
  color: var(--text-tertiary);
  font-size: 12px;
}
</style>
