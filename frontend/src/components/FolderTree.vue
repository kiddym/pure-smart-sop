<script setup lang="ts">
import { ElIcon } from 'element-plus'
import type { FolderTreeNode } from '@/types/folder'
import { folderIcon } from '@/utils/folderIcon'

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
    <template #default="{ node: treeNode, data: node }">
      <span class="ft-node">
        <el-icon class="ft-icon" :class="{ 'ft-icon--system': node.system }">
          <component :is="folderIcon(node, treeNode.expanded)" />
        </el-icon>
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
/* 引导图标：普通文件夹染暖琥珀（亲和）；系统文件夹的锁走中性灰、与暖色拉开层级；
   选中行统一染赤陶。hover 时图标轻微放大，给一点“可点”的手感。 */
.ft-icon {
  flex: none;
  font-size: 16px;
  color: var(--folder-amber);
  transition:
    color var(--dur-route) var(--ease-standard),
    transform var(--dur-route) var(--ease-standard);
}
.ft-icon--system {
  color: var(--text-secondary);
}
:deep(.el-tree-node__content:hover) .ft-icon {
  transform: scale(1.08);
}
:deep(.el-tree-node.is-current) > .el-tree-node__content .ft-icon {
  color: var(--accent);
}
@media (prefers-reduced-motion: reduce) {
  .ft-icon {
    transition: color var(--dur-route) var(--ease-standard);
  }
  :deep(.el-tree-node__content:hover) .ft-icon {
    transform: none;
  }
}
.ft-count {
  color: var(--text-tertiary);
  font-size: 12px;
}
</style>
