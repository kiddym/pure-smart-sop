// 导入向导树审查纯函数（Q351/Q354）。全部不可变（返回新树），便于 Vue 响应式 + 测试。

import type { ConfidenceTier, ImportNode, ParsedNode } from '@/types/parse'
import type { ContentType, MarkStatus } from '@/types/node'

// 向导内部树节点：仅保留可编辑 / 渲染所需字段（丢弃 order/level/parent_id/heading_source 等派生项）。
export interface WizardNode {
  id: string
  title: string
  content_type: ContentType
  rich_content: string
  skip_numbering: boolean
  mark_status: MarkStatus
  confidence_tier: ConfidenceTier
  children: WizardNode[]
}

export function buildWizardTree(nodes: ParsedNode[]): WizardNode[] {
  return nodes.map((n) => ({
    id: n.id,
    title: n.title,
    content_type: n.content_type,
    rich_content: n.rich_content,
    skip_numbering: n.skip_numbering,
    mark_status: n.mark_status,
    confidence_tier: n.confidence_tier,
    children: buildWizardTree(n.children),
  }))
}

export function cloneTree(nodes: WizardNode[]): WizardNode[] {
  return nodes.map((n) => ({ ...n, children: cloneTree(n.children) }))
}

export function findNode(nodes: WizardNode[], id: string): WizardNode | null {
  for (const n of nodes) {
    if (n.id === id) return n
    const hit = findNode(n.children, id)
    if (hit) return hit
  }
  return null
}

export function updateNode(
  nodes: WizardNode[],
  id: string,
  patch: Partial<Pick<WizardNode, 'title' | 'skip_numbering' | 'mark_status'>>,
): WizardNode[] {
  return nodes.map((n) => {
    if (n.id === id) return { ...n, ...patch, children: [...n.children] }
    return { ...n, children: updateNode(n.children, id, patch) }
  })
}

export function deleteNode(nodes: WizardNode[], id: string): WizardNode[] {
  return nodes
    .filter((n) => n.id !== id)
    .map((n) => ({ ...n, children: deleteNode(n.children, id) }))
}

// direction: -1 上移 / +1 下移；同级交换；边界 no-op。
export function moveNode(nodes: WizardNode[], id: string, direction: -1 | 1): WizardNode[] {
  const idx = nodes.findIndex((n) => n.id === id)
  if (idx !== -1) {
    const target = idx + direction
    if (target < 0 || target >= nodes.length) return nodes // 边界 no-op
    const next = [...nodes]
    ;[next[idx], next[target]] = [next[target], next[idx]]
    return next
  }
  return nodes.map((n) => ({ ...n, children: moveNode(n.children, id, direction) }))
}

export function countReview(nodes: WizardNode[]): number {
  return nodes.reduce(
    (acc, n) => acc + (n.mark_status === 'review' ? 1 : 0) + countReview(n.children),
    0,
  )
}

export function clearReview(nodes: WizardNode[]): WizardNode[] {
  return nodes.map((n) => ({
    ...n,
    mark_status: n.mark_status === 'review' ? 'unmarked' : n.mark_status,
    children: clearReview(n.children),
  }))
}

// 压成 POST /procedures/import 形态：丢弃向导内部字段 + 清 review（Q354，对齐后端 REVIEW_NOT_CLEARED）。
export function toImportNodes(nodes: WizardNode[]): ImportNode[] {
  return nodes.map((n) => ({
    title: n.title,
    content_type: n.content_type,
    rich_content: n.rich_content,
    skip_numbering: n.skip_numbering,
    mark_status: n.mark_status === 'review' ? 'unmarked' : n.mark_status,
    children: toImportNodes(n.children),
  }))
}
