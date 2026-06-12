import type { Node } from '@/types/node'

/** 层级深浅秩：L1<L2<L3<正文(叶子最深)。null(正文/步骤)记为最深。 */
function rank(level: number | null): number {
  return level === null ? 4 : level
}

/** 在扁平节点序列中算出「在 targetId 下方新增一个 newLevel 节点」应插入的下标。
 *  规则（避免窃取目标章节的现有子节点）：
 *   - 新节点比目标更深（rank 更大）→ 作为目标的首个子项，紧跟目标行（index+1）。
 *   - 否则（同级或更浅）→ 落到目标整棵子树之后。
 *  target 不存在 → 末尾追加（nodes.length）。
 *  nodes 假定按 sort_order 升序、depth 为派生层级（同 computeReorder）。 */
export function computeInsertIndex(
  nodes: Pick<Node, 'id' | 'depth' | 'heading_level'>[],
  targetId: string,
  newLevel: number | null,
): number {
  const ti = nodes.findIndex((n) => n.id === targetId)
  if (ti < 0) return nodes.length
  if (rank(newLevel) > rank(nodes[ti].heading_level)) return ti + 1
  let end = ti
  while (end + 1 < nodes.length && nodes[end + 1].depth > nodes[ti].depth) end++
  return end + 1
}
