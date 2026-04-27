/**
 * Platform superuser admin API (users, MCP keys, tool invocation logs).
 */

import {
  API,
  defaultOptions,
  readJsonOrEmpty,
  apiErrorMessage,
  fetchApiJson,
} from '../lib/apiFetch.js'

export async function getPlatformUsers() {
  const r = await fetch(`${API}/admin/users`, defaultOptions)
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

export async function patchPlatformUser(userId, patch) {
  const r = await fetch(`${API}/admin/users/${encodeURIComponent(userId)}`, {
    ...defaultOptions,
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

export async function patchPlatformUserSuperuser(userId, isSuperuser) {
  return patchPlatformUser(userId, { is_superuser: isSuperuser })
}

export async function createPlatformUser({ email, name, password }) {
  const body = {
    email: email.trim(),
    name: (name || '').trim() || 'User',
  }
  if (password && String(password).length > 0) body.password = password
  const r = await fetch(`${API}/admin/users`, {
    ...defaultOptions,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

export async function getPlatformUser(userId) {
  const r = await fetch(`${API}/admin/users/${encodeURIComponent(userId)}`, defaultOptions)
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

/**
 * Replace a user's study memberships (platform superuser). Roles: "admin" | "staff" (same as study admin UI).
 * @param {string} userId
 * @param {Array<{ study_id: string, role: string }>} memberships
 */
export async function putPlatformUserStudies(userId, memberships) {
  const r = await fetch(`${API}/admin/users/${encodeURIComponent(userId)}/studies`, {
    ...defaultOptions,
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ memberships }),
  })
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

export async function getPlatformSummary() {
  return fetchApiJson('/admin/platform-summary')
}

export async function getMcpToolNames() {
  const r = await fetch(`${API}/admin/mcp-tool-names`, defaultOptions)
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

export async function getMcpApiKeys() {
  const r = await fetch(`${API}/admin/mcp-api-keys`, defaultOptions)
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

export async function createMcpApiKey({ name, scopes, ownerUserId, expiresAt, allowedStudyIds }) {
  const r = await fetch(`${API}/admin/mcp-api-keys`, {
    ...defaultOptions,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: name || 'API key',
      scopes: scopes || [],
      owner_user_id: ownerUserId,
      allowed_study_ids: allowedStudyIds,
      expires_at: expiresAt,
    }),
  })
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

export async function patchMcpApiKey(keyId, patch) {
  const body = {}
  if (patch.name !== undefined) body.name = patch.name
  if (patch.expiresAt !== undefined) body.expires_at = patch.expiresAt
  if (patch.ownerUserId !== undefined) body.owner_user_id = patch.ownerUserId
  if (patch.clearAllowedStudyIds) body.clear_allowed_study_ids = true
  else if (patch.allowedStudyIds !== undefined) body.allowed_study_ids = patch.allowedStudyIds
  const r = await fetch(`${API}/admin/mcp-api-keys/${encodeURIComponent(keyId)}`, {
    ...defaultOptions,
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

export async function rotateMcpApiKey(keyId) {
  const r = await fetch(`${API}/admin/mcp-api-keys/${encodeURIComponent(keyId)}/rotate`, {
    ...defaultOptions,
    method: 'POST',
  })
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

export async function purgeToolInvocationLogs(olderThanDays) {
  const r = await fetch(`${API}/admin/tool-invocations/purge`, {
    ...defaultOptions,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ older_than_days: olderThanDays }),
  })
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

export async function revokeMcpApiKey(keyId) {
  const r = await fetch(`${API}/admin/mcp-api-keys/${encodeURIComponent(keyId)}/revoke`, {
    ...defaultOptions,
    method: 'POST',
  })
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}

/**
 * @param {object} [params]
 * @param {number} [params.limit]
 * @param {number} [params.offset]
 * @param {string} [params.from] ISO datetime
 * @param {string} [params.to] ISO datetime
 * @param {string} [params.apiKeyId]
 * @param {string} [params.tool]
 * @param {string} [params.studyId]
 * @param {number} [params.statusMin]
 * @param {number} [params.statusMax]
 */
export async function getToolInvocations(params = {}) {
  const q = new URLSearchParams()
  if (params.limit != null) q.set('limit', String(params.limit))
  if (params.offset != null) q.set('offset', String(params.offset))
  if (params.from) q.set('from', params.from)
  if (params.to) q.set('to', params.to)
  if (params.apiKeyId) q.set('api_key_id', params.apiKeyId)
  if (params.tool) q.set('tool', params.tool)
  if (params.studyId) q.set('study_id', params.studyId)
  if (params.statusMin != null) q.set('status_min', String(params.statusMin))
  if (params.statusMax != null) q.set('status_max', String(params.statusMax))
  const qs = q.toString()
  const r = await fetch(`${API}/admin/tool-invocations${qs ? `?${qs}` : ''}`, defaultOptions)
  if (!r.ok) {
    const err = await readJsonOrEmpty(r)
    throw new Error(apiErrorMessage(r, err))
  }
  return r.json()
}
