/**
 * Shared API base URL, cookie defaults, FastAPI error parsing, and optional JSON fetch helper.
 * Keeps a single place for backend URL normalization (see normalizeBackendBase).
 */

// Strip a trailing `/api` so we never request `/api/api/...` (FastAPI returns 404 for those URLs).
export function normalizeBackendBase(raw) {
  if (raw == null || raw === '') return ''
  let s = String(raw).trim()
  while (s.endsWith('/')) s = s.slice(0, -1)
  if (s.endsWith('/api')) s = s.slice(0, -4)
  return s
}

export const BACKEND_BASE = normalizeBackendBase(
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_BACKEND_URL) || ''
)

export const API = `${BACKEND_BASE}/api`

export const defaultOptions = { credentials: 'include' }

export async function readJsonOrEmpty(r) {
  return r.json().catch(() => ({}))
}

/** FastAPI may return `detail` as a string or a validation error array. */
export function apiErrorMessage(r, body) {
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (e && typeof e === 'object' && e.msg != null ? e.msg : JSON.stringify(e)))
      .join('; ')
  }
  if (detail != null && typeof detail === 'object') return JSON.stringify(detail)
  return r.statusText || `HTTP ${r.status}`
}

export function getAuthBase() {
  return BACKEND_BASE
}

/**
 * GET/POST JSON under `/api/...` with session cookies and unified error messages.
 * @param {string} path - e.g. `/admin/platform-summary`
 */
export async function fetchApiJson(path, init = {}) {
  const url = `${API}${path.startsWith('/') ? path : `/${path}`}`
  const r = await fetch(url, { ...defaultOptions, ...init })
  const data = await readJsonOrEmpty(r)
  if (!r.ok) throw new Error(apiErrorMessage(r, data))
  return data
}
