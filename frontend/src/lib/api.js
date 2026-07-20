/** API client — always calls /api/* (Vite proxies locally; Vercel same-origin). */

const BASE = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '')

async function json(res) {
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json()
}

export async function fetchDemo() {
  return json(await fetch(`${BASE}/demo/sample`))
}

export async function fetchDemoIngestPreview() {
  return json(await fetch(`${BASE}/demo/ingest-preview`))
}

export async function ingestFiles(fileA, fileB) {
  const form = new FormData()
  if (fileA) form.append('list_a_file', fileA)
  if (fileB) form.append('list_b_file', fileB)
  return json(await fetch(`${BASE}/ingest`, { method: 'POST', body: form }))
}

export async function ingestOneSide(side, file) {
  const form = new FormData()
  if (side === 'A') form.append('list_a_file', file)
  else form.append('list_b_file', file)
  return json(await fetch(`${BASE}/ingest`, { method: 'POST', body: form }))
}

export async function fetchPresets() {
  return json(await fetch(`${BASE}/presets`))
}

export async function runCompare(listA, listB, config) {
  return json(
    await fetch(`${BASE}/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ list_a: listA, list_b: listB, config }),
    }),
  )
}

export const CLASS_COLORS = {
  exact_match: '#2a9d8f',
  strong_fuzzy_match: '#2ec4b6',
  temporal_variant: '#e76f51',
  spatial_proximity_candidate: '#f4a261',
  ambiguous: '#7a93a0',
  weak_candidate: '#5c7380',
  unmatched: '#c44536',
  confirmed_match: '#2a9d8f',
  confirmed_temporal: '#e76f51',
  marked_distinct: '#c44536',
}

export const CLASS_LABELS = {
  exact_match: 'Exact',
  strong_fuzzy_match: 'Strong',
  temporal_variant: 'Temporal',
  spatial_proximity_candidate: 'Spatial',
  ambiguous: 'Ambiguous',
  weak_candidate: 'Weak',
  unmatched: 'Unmatched',
  confirmed_match: 'Merged',
  confirmed_temporal: 'Temporal merge',
  marked_distinct: 'Keep separate',
}

export function defaultConfig() {
  return {
    max_geo_distance_m: 350,
    min_name_similarity: 75,
    min_attr_similarity: 0.55,
    date_tolerance_days: 30,
    composite_threshold: 0.72,
    min_candidate_score: 0.4,
    require_category_match: false,
    name_scorer: 'token_set_ratio',
    weights: { geo: 0.3, name: 0.2, attr: 0.35, temporal: 0.15 },
  }
}
