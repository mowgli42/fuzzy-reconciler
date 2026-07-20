/** Category inventory metrics for operational QA of merge inflation/deflation. */

export function countByCategory(entities) {
  const map = {}
  for (const e of entities || []) {
    const cat = e.category || e.attributes?.category || 'uncategorized'
    map[cat] = (map[cat] || 0) + 1
  }
  return map
}

/**
 * Build inventory rows comparing List A, List B, working merge set, and a
 * projected count if all open (undecided) match pairs were merged.
 */
export function buildInventory({ listA, listB, matches, decisions, workingSet }) {
  const aCounts = countByCategory(listA)
  const bCounts = countByCategory(listB)
  const workingCounts = countByCategory(workingSet)

  const categories = new Set([
    ...Object.keys(aCounts),
    ...Object.keys(bCounts),
    ...Object.keys(workingCounts),
  ])

  // Projected: start from A+B, subtract one for each pair that is/will-be merged
  const projected = { ...aCounts }
  for (const [cat, n] of Object.entries(bCounts)) {
    projected[cat] = (projected[cat] || 0) + n
  }

  for (const m of matches || []) {
    const d = decisions?.[m.pair_id]
    const action = d?.action
    const willMerge =
      action === 'confirm_match' ||
      action === 'confirm_temporal' ||
      (!action &&
        ['exact_match', 'strong_fuzzy_match', 'temporal_variant'].includes(m.classification))
    if (!willMerge) continue
    const cat = m.entity_a?.category || m.entity_b?.category || 'uncategorized'
    projected[cat] = Math.max(0, (projected[cat] || 0) - 1)
    categories.add(cat)
  }

  const rows = [...categories]
    .sort()
    .map((category) => {
      const a = aCounts[category] || 0
      const b = bCounts[category] || 0
      const working = workingCounts[category] || 0
      const proj = projected[category] || 0
      const ceiling = Math.max(a, b)
      const floor = Math.min(a, b)
      let flag = null
      // Inflation: more in working/projected than either source alone suggests
      if (working > ceiling || proj > a + b) flag = 'inflation'
      else if (working > 0 && working < floor && a > 0 && b > 0) flag = 'deflation'
      else if (proj > ceiling && a > 0 && b > 0) flag = 'watch'
      return {
        category,
        list_a: a,
        list_b: b,
        working,
        projected: proj,
        ceiling,
        flag,
      }
    })

  const totals = rows.reduce(
    (acc, r) => {
      acc.list_a += r.list_a
      acc.list_b += r.list_b
      acc.working += r.working
      acc.projected += r.projected
      return acc
    },
    { list_a: 0, list_b: 0, working: 0, projected: 0 },
  )

  return { rows, totals, alerts: rows.filter((r) => r.flag === 'inflation' || r.flag === 'deflation') }
}
