import type { Component } from 'vue'
import { Folder, FolderOpened, Lock } from '@element-plus/icons-vue'

/** 文件夹树节点的引导图标：
 *  - 系统文件夹 → 锁（受保护，优先级最高，不随开合变化）
 *  - 普通文件夹展开且有子级 → 打开的文件夹
 *  - 其余（闭合 / 无子级）→ 闭合的文件夹
 *  仅依赖 system + children 长度，故用结构化入参（FolderTreeNode 天然满足）。 */
export function folderIcon(
  node: { system: boolean; children?: unknown[] },
  expanded: boolean,
): Component {
  if (node.system) return Lock
  const hasChildren = !!node.children?.length
  return expanded && hasChildren ? FolderOpened : Folder
}
