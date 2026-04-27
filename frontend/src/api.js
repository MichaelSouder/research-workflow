/**
 * API client for Research Workflow backend.
 * All requests send credentials (cookies) for auth.
 * In dev we use same-origin (Vite proxies /api and /auth to backend port, default 48721) so the session cookie works.
 */

import {
  API,
  BACKEND_BASE,
  defaultOptions,
  getAuthBase,
  fetchApiJson,
  readJsonOrEmpty,
  apiErrorMessage,
} from './lib/apiFetch.js'

export { getAuthBase, fetchApiJson }

const DEV_BYPASS_STATUS_TIMEOUT_MS = 8000
const DEFAULT_BACKEND_PORT = '48721'

function localApiFallbackOrigin() {
  const p =
    typeof import.meta !== 'undefined' && import.meta.env?.VITE_BACKEND_PORT
      ? String(import.meta.env.VITE_BACKEND_PORT)
      : DEFAULT_BACKEND_PORT
  return `http://127.0.0.1:${p}`
}

function shouldTryLocalApiFallback() {
  if (String(BACKEND_BASE || '').trim()) return false
  return Boolean(typeof import.meta !== 'undefined' && import.meta.env?.DEV)
}

function parseBypassJsonResponse(r, data) {
  const ct = r.headers.get('content-type') || ''
  if (!r.ok) return { ok: false, reason: 'http', status: r.status }
  if (!ct.includes('application/json')) return { ok: false, reason: 'not_json' }
  if (typeof data?.bypassAvailable !== 'boolean') return { ok: false, reason: 'bad_body' }
  return { ok: true, available: data.bypassAvailable }
}

/**
 * Ask the backend if GET /auth/dev-login is allowed.
 * @returns {{ available: boolean, fetchOk: boolean, httpStatus?: number }}
 * `fetchOk` false means the request failed (backend down, wrong VITE_BACKEND_URL, or CORS) — not that bypass is disabled in .env.
 */
export async function getDevBypassStatus() {
  const ac = new AbortController()
  const tid = setTimeout(() => ac.abort(), DEV_BYPASS_STATUS_TIMEOUT_MS)

  const tryOnce = async (url) => {
    const r = await fetch(url, { ...defaultOptions, signal: ac.signal })
    const data = await r.json().catch(() => null)
    return parseBypassJsonResponse(r, data)
  }

  const primary = `${BACKEND_BASE || ''}/auth/dev-bypass-status`
  const fallbackBase = localApiFallbackOrigin()
  const direct = `${fallbackBase}/auth/dev-bypass-status`

  try {
    let result = await tryOnce(primary)
    if (result.ok) return { available: result.available, fetchOk: true }

    if (shouldTryLocalApiFallback()) {
      try {
        result = await tryOnce(direct)
        if (result.ok) return { available: result.available, fetchOk: true }
      } catch {
        /* primary may have been HTML 404; direct still fails */
      }
    }

    return {
      available: false,
      fetchOk: false,
      httpStatus: result.status,
    }
  } catch {
    if (shouldTryLocalApiFallback()) {
      try {
        const result = await tryOnce(direct)
        if (result.ok) return { available: result.available, fetchOk: true }
      } catch {
        /* ignore */
      }
    }
    return { available: false, fetchOk: false }
  } finally {
    clearTimeout(tid)
  }
}

/** @deprecated Use getDevBypassStatus for error distinction */
export async function getDevBypassAvailable() {
  const s = await getDevBypassStatus()
  return s.available
}

/**
 * @param {AbortSignal} [signal] - abort or timeout to avoid hanging forever when the backend is unreachable
 */
export async function getAuthMe(signal) {
  const r = await fetch(`${BACKEND_BASE || ''}/auth/me`, { ...defaultOptions, signal })
  if (r.status === 401) return null
  if (!r.ok) throw new Error(r.statusText)
  const data = await r.json()
  return {
    ...data,
    isSuperuser: Boolean(data.isSuperuser ?? data.is_superuser),
  }
}

export function getLogoutUrl() {
  return `${BACKEND_BASE}/auth/logout`
}

export async function getStatus() {
  const r = await fetch(`${API}/status`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function getActivity() {
  const r = await fetch(`${API}/activity`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function getErrors() {
  const r = await fetch(`${API}/errors`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function startRun(configOverrides = null) {
  const r = await fetch(`${API}/run/start`, {
    ...defaultOptions,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(configOverrides ? { config_overrides: configOverrides } : {}),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function stopRun() {
  const r = await fetch(`${API}/run/stop`, { ...defaultOptions, method: 'POST' })
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function getConfig(revealSecrets = false) {
  const url = revealSecrets ? `${API}/config?reveal_secrets=true` : `${API}/config`
  const r = await fetch(url, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function saveConfig(config, persist = false) {
  const r = await fetch(`${API}/config`, {
    ...defaultOptions,
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config, persist }),
  })
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function getStudies() {
  const r = await fetch(`${API}/studies`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

/** Studies with status and pipelines for the dashboard. */
export async function getStudiesDashboard() {
  const r = await fetch(`${API}/studies/dashboard`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function getStudy(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function getStudyConfig(studyId, revealSecrets = false) {
  const url = revealSecrets
    ? `${API}/studies/${encodeURIComponent(studyId)}/config?reveal_secrets=true`
    : `${API}/studies/${encodeURIComponent(studyId)}/config`
  const r = await fetch(url, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function saveStudyConfig(studyId, config, persist = false) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/config`, {
    ...defaultOptions,
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config, persist }),
  })
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function getStudyStatus(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/status`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function getStudyActivity(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/activity`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function getStudyErrors(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/errors`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

// ——— Pipelines (graph definitions per study) ———
export async function getStudyPipelines(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/pipelines`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function getStudyPipeline(studyId, pipelineId) {
  const r = await fetch(
    `${API}/studies/${encodeURIComponent(studyId)}/pipelines/${encodeURIComponent(pipelineId)}`,
    defaultOptions
  )
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

/**
 * Subscribe to pipeline events (SSE) for hot reload. Calls onEvent(payload) for each event.
 * Optional onStatus('connected' | 'reconnecting' | 'disconnected'). Reconnects with backoff on disconnect.
 * @returns {{ unsubscribe: () => void }}
 */
export function subscribePipelineStream(studyId, pipelineId, { onEvent, onStatus } = {}) {
  let cancelled = false
  let controller = null
  let backoffMs = 1000
  const maxBackoffMs = 30000

  async function run() {
    while (!cancelled) {
      controller = new AbortController()
      const url = `${API}/studies/${encodeURIComponent(studyId)}/pipelines/stream${pipelineId ? `?pipeline_id=${encodeURIComponent(pipelineId)}` : ''}`
      try {
        const r = await fetch(url, { ...defaultOptions, signal: controller.signal })
        if (cancelled) return
        if (!r.ok) {
          throw new Error(r.statusText || r.status)
        }
        if (onStatus) onStatus('connected')
        const reader = r.body?.getReader()
        if (!reader) return
        const decoder = new TextDecoder()
        let buffer = ''
        while (!cancelled) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const payload = JSON.parse(line.slice(6))
                onEvent?.(payload)
              } catch {
                /* ignore malformed SSE data line */
              }
            }
          }
        }
      } catch (e) {
        if (cancelled || e?.name === 'AbortError') return
      }
      if (cancelled) return
      if (onStatus) onStatus('reconnecting')
      await new Promise((r) => setTimeout(r, backoffMs))
      backoffMs = Math.min(backoffMs * 2, maxBackoffMs)
    }
    if (onStatus) onStatus('disconnected')
  }

  run()

  return {
    unsubscribe() {
      cancelled = true
      if (controller) controller.abort()
    },
  }
}

export async function saveStudyPipeline(studyId, pipelineId, { name, is_default, nodes, edges }) {
  const r = await fetch(
    `${API}/studies/${encodeURIComponent(studyId)}/pipelines/${encodeURIComponent(pipelineId)}`,
    {
      ...defaultOptions,
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, is_default: is_default ?? false, nodes, edges }),
    }
  )
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function createStudyPipeline(studyId, { name, is_default, nodes, edges }) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/pipelines`, {
    ...defaultOptions,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      is_default: is_default ?? false,
      nodes: nodes ?? [],
      edges: edges ?? [],
    }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function deleteStudyPipeline(studyId, pipelineId) {
  const r = await fetch(
    `${API}/studies/${encodeURIComponent(studyId)}/pipelines/${encodeURIComponent(pipelineId)}`,
    { ...defaultOptions, method: 'DELETE' }
  )
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function startStudyRun(studyId, options = null) {
  const body = {}
  // Support options = { config_overrides, pipeline_id } or legacy: second arg = config_overrides object
  if (options && typeof options === 'object') {
    if ('config_overrides' in options) body.config_overrides = options.config_overrides
    if ('pipeline_id' in options) body.pipeline_id = options.pipeline_id
    if (!('config_overrides' in options) && !('pipeline_id' in options) && Object.keys(options).length)
      body.config_overrides = options
  }
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/run/start`, {
    ...defaultOptions,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function stopStudyRun(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/run/stop`, {
    ...defaultOptions,
    method: 'POST',
  })
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function getStudyUsers(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/users`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function setStudyUsers(studyId, users) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/users`, {
    ...defaultOptions,
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ users }),
  })
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function patchStudy(studyId, { name, description }) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}`, {
    ...defaultOptions,
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  })
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function createStudy({ name, description }) {
  const r = await fetch(`${API}/studies`, {
    ...defaultOptions,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description: description || null }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export * from './api/platformAdmin.js'

export async function getIntegrationContext() {
  const r = await fetch(`${API}/integrations/context`, defaultOptions)
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

export async function getMyMcpApiKeys() {
  const r = await fetch(`${API}/integrations/mcp-api-keys`, defaultOptions)
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  const data = await r.json()
  const rawList = Array.isArray(data) ? data : data.keys ?? []
  const keys = rawList
    .map((x) => ({
      id: String(x?.id ?? '').trim(),
      name: String(x?.name ?? 'API key').trim() || 'API key',
      keyPrefix: String(x?.keyPrefix ?? x?.key_prefix ?? '—').trim() || '—',
      scopes: x?.scopes,
      allowedStudyIds: x?.allowedStudyIds ?? x?.allowed_study_ids,
      createdAt: x?.createdAt ?? x?.created_at,
      expiresAt: x?.expiresAt ?? x?.expires_at,
    }))
    .filter((x) => x.id)
  const otherRaw = data.activeKeysNotOwnedByYou ?? data.active_keys_not_owned_by_you
  const activeKeysNotOwnedByYou = Array.isArray(otherRaw)
    ? otherRaw.map((x) => ({
        id: String(x?.id ?? '').trim(),
        name: String(x?.name ?? '').trim() || 'API key',
        keyPrefix: String(x?.keyPrefix ?? x?.key_prefix ?? '').trim(),
        ownerUserId: x?.ownerUserId ?? x?.owner_user_id ?? null,
      }))
    : []

  const inactOtherRaw = data.inactiveKeysNotOwnedByYou ?? data.inactive_keys_not_owned_by_you
  const inactiveKeysNotOwnedByYou = Array.isArray(inactOtherRaw)
    ? inactOtherRaw.map((x) => ({
        id: String(x?.id ?? '').trim(),
        name: String(x?.name ?? '').trim() || 'API key',
        keyPrefix: String(x?.keyPrefix ?? x?.key_prefix ?? '').trim(),
        ownerUserId: x?.ownerUserId ?? x?.owner_user_id ?? null,
        reason: String(x?.reason ?? 'inactive'),
      }))
    : []

  const ownedRaw = data.ownedButInactive ?? data.owned_but_inactive
  const ownedButInactive = Array.isArray(ownedRaw)
    ? ownedRaw.map((x) => ({
        id: String(x?.id ?? '').trim(),
        name: String(x?.name ?? '').trim() || 'API key',
        keyPrefix: String(x?.keyPrefix ?? x?.key_prefix ?? '').trim(),
        reason: String(x?.reason ?? 'inactive'),
        expiresAt: x?.expiresAt ?? x?.expires_at ?? null,
        revokedAt: x?.revokedAt ?? x?.revoked_at ?? null,
      }))
    : []

  return {
    keys,
    viewerUserId: data.viewerUserId ?? data.viewer_user_id ?? null,
    activeKeysNotOwnedByYou,
    inactiveKeysNotOwnedByYou,
    ownedButInactive,
  }
}

/**
 * @param {{ apiKeyId: string, apiKeySecret: string }} params
 * @returns {Promise<Blob>}
 */
export async function downloadClaudeIntegrationBundle({ apiKeyId, apiKeySecret }) {
  const r = await fetch(`${API}/integrations/bundles/claude`, {
    ...defaultOptions,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key_id: apiKeyId, api_key_secret: apiKeySecret }),
  })
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.blob()
}

export async function addStudyUserByEmail(studyId, { email, role }) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/users/add`, {
    ...defaultOptions,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim(), role: role || 'staff' }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function deleteStudy(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}`, {
    ...defaultOptions,
    method: 'DELETE',
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function getStudyBoxConfigStatus(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/box-config`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function putStudyBoxConfig(studyId, configObject) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/box-config`, {
    ...defaultOptions,
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(configObject),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function getStudyBoxFolders(studyId, rootId = '0') {
  const r = await fetch(
    `${API}/studies/${encodeURIComponent(studyId)}/box/folders?root=${encodeURIComponent(rootId)}`,
    defaultOptions
  )
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function getStudyGridStudies(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/grid/studies`, defaultOptions)
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function getGridStudies() {
  const r = await fetch(`${API}/grid/studies`, defaultOptions)
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function getBoxFolders(rootId = '0') {
  const r = await fetch(`${API}/box/folders?root=${encodeURIComponent(rootId)}`, defaultOptions)
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    const msg = err.detail || r.statusText
    if (r.status === 404) {
      throw new Error(
        'Box folders API not found (404). Restart the backend server: from project root run "python run_backend.py" (default port 48721)'
      )
    }
    throw new Error(msg)
  }
  return r.json()
}

// ——— Distribution (mailing list, send/delete) ——— study-scoped

export async function getStudyDistributionContacts(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/distribution/contacts`, defaultOptions)
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function getStudyDistributionCheck(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/distribution/check`, defaultOptions)
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function getStudyDistributionStatus(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/distribution/status`, defaultOptions)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

export async function getStudyDistributionDistributions(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/distribution/distributions`, defaultOptions)
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function getStudyDistributionSendPreview(studyId) {
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/distribution/send-preview`, defaultOptions)
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

/**
 * @param {object} [options] - Optional: { limit?: number, contactIndices?: number[], bypassTimeSlot?: boolean }
 */
export async function postStudyDistributionSend(studyId, options = null) {
  const body = options && (options.limit != null || options.contactIndices != null || options.bypassTimeSlot)
    ? {
        ...(options.limit != null && { limit: options.limit }),
        ...(options.contactIndices != null && { contactIndices: options.contactIndices }),
        ...(options.bypassTimeSlot === true && { bypassTimeSlot: true }),
      }
    : undefined
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/distribution/send`, {
    ...defaultOptions,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

/**
 * @param {object} [options] - Optional: { index?: number, contactId?: string, allUnsent?: boolean }
 */
export async function postStudyDistributionDeleteUnsent(studyId, options = null) {
  const body = options != null && typeof options === 'object'
    ? {
        ...(options.index != null && { index: options.index }),
        ...(options.contactId != null && options.contactId !== '' && { contactId: options.contactId }),
        ...(options.allUnsent === true && { allUnsent: true }),
      }
    : options === null || options === undefined
      ? {}
      : { index: options }
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/distribution/delete-unsent`, {
    ...defaultOptions,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

/**
 * @param {object} [options] - Optional: { format?: 'json' | 'csv' }
 */
export async function postStudyDistributionExport(studyId, options = null) {
  const body = options?.format ? { format: options.format } : undefined
  const r = await fetch(`${API}/studies/${encodeURIComponent(studyId)}/distribution/export`, {
    ...defaultOptions,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}

export async function patchStudyDistributionContact(studyId, contactId, embeddedData) {
  const r = await fetch(
    `${API}/studies/${encodeURIComponent(studyId)}/distribution/contacts/${encodeURIComponent(contactId)}`,
    {
      ...defaultOptions,
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ embeddedData }),
    }
  )
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}
