/** Browser-local session persistence for the multi-user Vercel demo.
 * Server remains stateless. Optional future: PERSISTENCE=database for shared stores.
 */

const MODE_KEY = 'fr-persistence-mode'
const SESSION_KEY = 'fr-session-v1'

/** @returns {'browser' | 'none'} */
export function getPersistenceMode() {
  try {
    const v = localStorage.getItem(MODE_KEY)
    if (v === 'none' || v === 'browser') return v
  } catch {
    /* ignore */
  }
  return 'browser'
}

export function setPersistenceMode(mode) {
  localStorage.setItem(MODE_KEY, mode === 'none' ? 'none' : 'browser')
}

export function loadSession() {
  if (getPersistenceMode() !== 'browser') return null
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function saveSession(partial) {
  if (getPersistenceMode() !== 'browser') return
  try {
    const prev = loadSession() || {}
    const next = {
      ...prev,
      ...partial,
      saved_at: new Date().toISOString(),
    }
    localStorage.setItem(SESSION_KEY, JSON.stringify(next))
  } catch (e) {
    console.warn('session save failed (quota?)', e)
  }
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY)
}

export function persistenceLabel(mode = getPersistenceMode()) {
  if (mode === 'none') return 'History off (this tab only)'
  return 'Browser cache (this device only — not shared between users)'
}
