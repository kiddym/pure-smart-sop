interface ReviewRow {
  id: string
  mark_status: string
}

/**
 * 文档序里 currentId 之后第一个满足 predicate 的行 id（环绕）。
 * currentId 为 null 或不在 rows 中 → 取第一个命中。无命中 → null。
 */
export function nextRowId<T extends { id: string }>(
  rows: T[],
  currentId: string | null,
  predicate: (r: T) => boolean,
): string | null {
  const hits = rows.filter(predicate)
  if (hits.length === 0) return null
  if (currentId === null) return hits[0].id
  const curIdx = rows.findIndex((r) => r.id === currentId)
  if (curIdx === -1) return hits[0].id
  for (let i = 1; i <= rows.length; i++) {
    const r = rows[(curIdx + i) % rows.length]
    if (predicate(r)) return r.id
  }
  return hits[0].id
}

/**
 * 文档序里 currentId 之后的下一个 review 行 id（环绕）。无 review → null。
 */
export function nextReviewId(rows: ReviewRow[], currentId: string | null): string | null {
  return nextRowId(rows, currentId, (r) => r.mark_status === 'review')
}
