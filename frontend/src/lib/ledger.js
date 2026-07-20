/** Persistent decline / keep-separate ledger for cross-run awareness. */

const STORAGE_KEY = 'fr-decline-ledger-v1'

export function entityFingerprint(ent) {
  if (!ent) return ''
  const name = String(ent.name || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
  const lat = ent.lat != null ? Number(ent.lat).toFixed(4) : ''
  const lon = ent.lon != null ? Number(ent.lon).toFixed(4) : ''
  const cat = String(ent.category || '')
    .trim()
    .toLowerCase()
  return `${name}|${lat}|${lon}|${cat}`
}

export function pairFingerprint(a, b) {
  const fa = entityFingerprint(a)
  const fb = entityFingerprint(b)
  return [fa, fb].sort().join('::')
}

export function loadDeclineLedger() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveDeclineLedger(entries) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, 500)))
}

export function recordDecline(pair, notes = '') {
  const entries = loadDeclineLedger()
  const fp = pairFingerprint(pair.entity_a, pair.entity_b)
  const next = [
    {
      fingerprint: fp,
      name_a: pair.entity_a?.name,
      name_b: pair.entity_b?.name,
      category: pair.entity_a?.category || pair.entity_b?.category || null,
      classification: pair.classification,
      composite_score: pair.scores?.composite_score,
      notes,
      declined_at: new Date().toISOString(),
    },
    ...entries.filter((e) => e.fingerprint !== fp),
  ]
  saveDeclineLedger(next)
  return next
}

export function removeDecline(pair) {
  const fp = pairFingerprint(pair.entity_a, pair.entity_b)
  const next = loadDeclineLedger().filter((e) => e.fingerprint !== fp)
  saveDeclineLedger(next)
  return next
}

export function findPriorDecline(pair, ledger) {
  const fp = pairFingerprint(pair.entity_a, pair.entity_b)
  return ledger.find((e) => e.fingerprint === fp) || null
}

export function declineTrendByCategory(ledger) {
  const map = {}
  for (const e of ledger) {
    const cat = e.category || 'uncategorized'
    map[cat] = (map[cat] || 0) + 1
  }
  return Object.entries(map)
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count)
}
