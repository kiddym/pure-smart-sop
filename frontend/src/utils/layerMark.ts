export type LayerRole = 'chapter_1' | 'chapter_2' | 'chapter_3' | 'content' | 'keep'

/** 文档序里参与层级标定的行——含章节与叶子（step / content）。 */
export interface LayerRow {
  id: string
  kind: 'chapter' | 'step' | 'content'
  level: number // chapter 当前层级（叶子行 level=0 占位）
  hasLeafChildren: boolean // 仅 chapter 有意义：挂了步骤/内容块 → 不可降为 content
}

/** 应用层级后单个行的目标归属（tagged union）。 */
export type LayerUpdate =
  | { kind: 'reorder'; parent_id: string | null; sort_order: number; level: number }
  | { kind: 'to-content'; parent_id: string | null; sort_order: number; sourceTitle: string }
  | { kind: 'to-chapter'; parent_id: string | null; sort_order: number; level: number }
  | { kind: 'leaf-reparent'; parent_id: string | null; sort_order: number }

/** 默认角色：chapter 用 level 预填；叶子行预填 keep。 */
export function defaultLayerRole(row: LayerRow): LayerRole {
  if (row.kind !== 'chapter') return 'keep'
  const lv = Math.min(3, Math.max(1, row.level))
  return `chapter_${lv}` as LayerRole
}

function roleLevel(role: LayerRole): number {
  return role === 'chapter_3' ? 3 : role === 'chapter_2' ? 2 : 1
}

function effectiveRole(row: LayerRow, roleMap: Map<string, LayerRole>): LayerRole {
  const role = roleMap.get(row.id) ?? defaultLayerRole(row)
  if (row.kind === 'chapter') {
    // 章节：content 角色受 hasLeafChildren 约束
    if (role === 'content' && row.hasLeafChildren) return defaultLayerRole(row)
    // 章节不可选 'keep'，夹回默认
    if (role === 'keep') return defaultLayerRole(row)
    return role
  }
  // 叶子：'content' 在叶子上无意义，夹回 keep
  if (role === 'content') return 'keep'
  return role
}

/**
 * 由文档序行 + roleMap 算每个章节节点的目标 {parent_id, toContentStep, sort_order}。
 * l1/l2/l3 走位：chapter_2 无一级父→根；chapter_3 无二级父→挂一级/根；content 挂最近章节、作叶子。
 * content 行不更新 l1/l2/l3 上下文（其后代会挂到上一个标题）。
 * TODO(layer-overlay Task 2/3): rewrite to emit new LayerUpdate shape
 */
export function computeLayerUpdates(
  rows: LayerRow[],
  roleMap: Map<string, LayerRole>,
): Map<string, LayerUpdate> {
  const out = new Map<string, any>()
  let l1: string | null = null
  let l2: string | null = null
  let l3: string | null = null
  const sortCounter = new Map<string | null, number>()
  const nextSort = (p: string | null): number => {
    const n = sortCounter.get(p) ?? 0
    sortCounter.set(p, n + 1)
    return n
  }
  for (const row of rows) {
    const role = effectiveRole(row, roleMap)
    if (role === 'content') {
      const parent = l3 ?? l2 ?? l1
      out.set(row.id, { parent_id: parent, toContentStep: true, sort_order: nextSort(parent) })
      continue
    }
    const level = roleLevel(role)
    let parent: string | null
    if (level >= 3 && l2) {
      parent = l2
      l3 = row.id
    } else if (level >= 2 && l1) {
      parent = l1
      l2 = row.id
      l3 = null
    } else {
      parent = null
      l1 = row.id
      l2 = null
      l3 = null
    }
    out.set(row.id, { parent_id: parent, toContentStep: false, sort_order: nextSort(parent) })
  }
  return out as Map<string, LayerUpdate>
}

/** 「所见即所选」缩进：章节 = level-1；content = 当前标题层级。 */
export function computeLayerIndents(
  rows: LayerRow[],
  roleMap: Map<string, LayerRole>,
): Map<string, number> {
  const map = new Map<string, number>()
  let headingLevel = 0
  for (const row of rows) {
    const role = effectiveRole(row, roleMap)
    if (role === 'content') {
      map.set(row.id, headingLevel)
    } else {
      const lv = roleLevel(role)
      map.set(row.id, lv - 1)
      headingLevel = lv
    }
  }
  return map
}
