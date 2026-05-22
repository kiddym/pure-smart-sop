// 叶子文件夹采集（仅非系统、无子、含 prefix 的文件夹可存程序）。

import type { FolderTreeNode } from '@/types/folder'

export interface LeafFolderOption {
  id: string
  label: string
  prefix: string
}

export function collectLeafFolders(
  nodes: FolderTreeNode[],
  acc: LeafFolderOption[] = [],
): LeafFolderOption[] {
  for (const n of nodes) {
    if (!n.system && n.children.length === 0 && n.prefix) {
      acc.push({ id: n.id, label: n.full_path, prefix: n.prefix })
    }
    if (n.children.length) collectLeafFolders(n.children, acc)
  }
  return acc
}
