import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import {
  downloadClaudeIntegrationBundle,
  getIntegrationContext,
  getMcpApiKeys,
  getMyMcpApiKeys,
} from '../api'
import Breadcrumb from '../components/Breadcrumb'
import PageHeader from '../components/PageHeader'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { Loader2 } from 'lucide-react'

export default function IntegrationsPage() {
  const { user, loading: authLoading, isSuperuser } = useAuth()
  const [ctx, setCtx] = useState(null)
  const [keys, setKeys] = useState([])
  const [viewerUserId, setViewerUserId] = useState(null)
  const [keysOwnedByOthers, setKeysOwnedByOthers] = useState([])
  const [inactiveKeysOwnedByOthers, setInactiveKeysOwnedByOthers] = useState([])
  const [ownedButInactive, setOwnedButInactive] = useState([])
  const [adminMcpKeyTotal, setAdminMcpKeyTotal] = useState(null)
  const [loadErr, setLoadErr] = useState(null)
  const [loading, setLoading] = useState(true)
  const [bundleKeyId, setBundleKeyId] = useState('')
  const [bundleSecret, setBundleSecret] = useState('')
  const [downloading, setDownloading] = useState(false)

  const load = useCallback(async () => {
    setLoadErr(null)
    const [c, k] = await Promise.all([getIntegrationContext(), getMyMcpApiKeys()])
    setCtx(c)
    setKeys(k.keys || [])
    setViewerUserId(k.viewerUserId ?? null)
    setKeysOwnedByOthers(k.activeKeysNotOwnedByYou || [])
    setInactiveKeysOwnedByOthers(k.inactiveKeysNotOwnedByYou || [])
    setOwnedButInactive(k.ownedButInactive || [])
  }, [])

  useEffect(() => {
    if (!keys.length) {
      setBundleKeyId('')
      return
    }
    setBundleKeyId((prev) => (prev && keys.some((x) => x.id === prev) ? prev : keys[0].id))
  }, [keys])

  useEffect(() => {
    if (authLoading || !user) {
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    ;(async () => {
      try {
        await load()
      } catch (e) {
        if (!cancelled) {
          let msg = e.message || 'Could not load integrations.'
          if (/not found|404/i.test(msg)) {
            msg +=
              " Stop every old backend process, start this repo's backend (e.g. uv run python run_backend.py on BACKEND_PORT, default 48721), then hard-refresh. Open http://127.0.0.1:48721/api/integrations/ping — expect JSON ok:true. If that URL 404s, the wrong server or an old Docker image is still running."
          }
          setLoadErr(msg)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [authLoading, user, load])

  useEffect(() => {
    if (authLoading || !user) return
    const refresh = () => {
      if (document.visibilityState !== 'visible') return
      load().catch((e) => setLoadErr(e.message || 'Could not refresh keys.'))
    }
    document.addEventListener('visibilitychange', refresh)
    return () => document.removeEventListener('visibilitychange', refresh)
  }, [authLoading, user, load])

  useEffect(() => {
    if (loading || loadErr || keys.length > 0 || !isSuperuser) {
      if (!isSuperuser) setAdminMcpKeyTotal(null)
      return
    }
    let cancelled = false
    getMcpApiKeys()
      .then((r) => {
        if (!cancelled) setAdminMcpKeyTotal(Array.isArray(r.keys) ? r.keys.length : 0)
      })
      .catch(() => {
        if (!cancelled) setAdminMcpKeyTotal(null)
      })
    return () => {
      cancelled = true
    }
  }, [loading, loadErr, keys.length, isSuperuser])

  const handleDownloadClaude = async () => {
    if (!bundleKeyId || !bundleSecret.trim()) {
      toast.error('Choose an API key and paste the secret (shown once when the key was created).')
      return
    }
    setDownloading(true)
    try {
      const blob = await downloadClaudeIntegrationBundle({
        apiKeyId: bundleKeyId,
        apiKeySecret: bundleSecret.trim(),
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'research-workflow-claude-mcp-bundle.zip'
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Bundle downloaded.')
      setBundleSecret('')
    } catch (e) {
      toast.error(e.message || 'Download failed.')
    } finally {
      setDownloading(false)
    }
  }

  if (authLoading || !user) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted-foreground">
        {authLoading ? <Loader2 className="size-8 animate-spin" /> : 'Redirecting…'}
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <main className="mx-auto max-w-4xl space-y-6 p-4 md:p-6">
        <Breadcrumb
          items={[{ label: 'Dashboard', to: '/studies' }, { label: 'Integrations' }]}
          className="mb-2"
        />
        <PageHeader
          title="Integrations"
          description="Connect Claude Desktop or ChatGPT to the Research Workflow tool API. Sensitive reads are masked on the server when data proxy is enabled for your account."
        />

        {loading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            Loading…
          </div>
        ) : loadErr ? (
          <p className="text-destructive">{loadErr}</p>
        ) : (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Claude Desktop (MCP zip)</CardTitle>
                <CardDescription>
                  Download a zip with a small Python MCP server that forwards tool calls to this deployment over HTTPS
                  using your API key. Install <code className="text-xs">mcp</code> and{' '}
                  <code className="text-xs">httpx</code> (see <code className="text-xs">requirements-bridge.txt</code>{' '}
                  in the zip).
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-muted-foreground text-xs">
                  Session user id (from API):{' '}
                  <span className="font-mono text-foreground">{viewerUserId || user.id || '—'}</span>
                  {keys.length > 0 ? (
                    <span className="text-foreground"> · {keys.length} owned MCP key(s) loaded</span>
                  ) : (
                    <span> · 0 keys returned for this account</span>
                  )}
                </p>

                {!keys.length ? (
                  <div className="space-y-2 text-sm text-muted-foreground">
                    <p>
                      Signed in as <span className="font-medium text-foreground">{user.email}</span>
                      {user.id ? (
                        <>
                          {' '}
                          <span className="font-mono text-xs">({user.id})</span>
                        </>
                      ) : null}
                      . Only keys whose Owner matches your user id appear here (and they must be active / not
                      expired).
                    </p>
                    {ownedButInactive.length > 0 ? (
                      <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-xs">
                        <p className="mb-2 font-medium text-foreground">
                          You own {ownedButInactive.length} MCP key(s) that are not active (expired or revoked). They do
                          not appear in the download list until renewed or replaced.
                        </p>
                        <ul className="space-y-1 font-mono text-[11px] text-muted-foreground">
                          {ownedButInactive.map((row) => (
                            <li key={row.id}>
                              {row.name} · {row.reason}
                              {row.expiresAt ? ` · expires ${row.expiresAt}` : ''}
                            </li>
                          ))}
                        </ul>
                        <p className="mt-2">
                          <Link to="/platform/api-keys" className="font-medium text-foreground underline">
                            Platform → API keys
                          </Link>{' '}
                          → Edit → set a future expiry, or create a new key (requires expiry + at least one study, then
                          click Create Key).
                        </p>
                      </div>
                    ) : null}
                    {isSuperuser ? (
                      <div className="space-y-3">
                        <p>
                          Go to{' '}
                          <Link to="/platform/api-keys" className="font-medium text-foreground underline">
                            Platform → API keys
                          </Link>{' '}
                          → Edit each key and set <span className="font-medium text-foreground">Owner</span> to the
                          session user id above (or pick &quot;Dev User (dev@local)&quot; whose id matches — see short
                          id in the owner dropdown).
                        </p>
                        {adminMcpKeyTotal != null && adminMcpKeyTotal > 0 && keysOwnedByOthers.length === 0 ? (
                          <p className="text-xs text-muted-foreground">
                            Admin view: this deployment has <span className="font-medium text-foreground">{adminMcpKeyTotal}</span>{' '}
                            MCP key row(s) total. Check the panels below for keys assigned to other users or
                            expired/revoked rows. Otherwise finish Create Key (expiry + study, then Create).
                          </p>
                        ) : null}
                        {inactiveKeysOwnedByOthers.length > 0 ? (
                          <div className="rounded-md border border-border bg-muted/40 p-3 text-xs">
                            <p className="mb-2 font-medium text-foreground">
                              Inactive MCP keys (expired/revoked) owned by someone else (
                              {inactiveKeysOwnedByOthers.length}):
                            </p>
                            <ul className="space-y-1 font-mono text-[11px] text-muted-foreground">
                              {inactiveKeysOwnedByOthers.map((row) => (
                                <li key={row.id}>
                                  {row.name} · {row.reason} · ownerUserId:{' '}
                                  <span className="text-foreground">{row.ownerUserId || '(none)'}</span>
                                </li>
                              ))}
                            </ul>
                            <p className="mt-2 text-muted-foreground">
                              These never appear in your download list. Rotate or create a new key with Owner = your
                              session id, or edit Owner if you intend to use this account for Integrations.
                            </p>
                          </div>
                        ) : null}
                        {keysOwnedByOthers.length > 0 ? (
                          <div className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-xs">
                            <p className="mb-2 font-medium text-foreground">
                              Active MCP keys in this environment owned by someone else ({keysOwnedByOthers.length}
                              ):
                            </p>
                            <ul className="space-y-1 font-mono text-[11px] text-muted-foreground">
                              {keysOwnedByOthers.map((row) => (
                                <li key={row.id}>
                                  {row.name} · prefix {row.keyPrefix || '—'} · ownerUserId:{' '}
                                  <span className="text-foreground">{row.ownerUserId || '(none)'}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <p>Ask a platform superuser to set you as Owner on an MCP API key.</p>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="grid gap-2">
                      <Label htmlFor="int-key">API key</Label>
                      <select
                        id="int-key"
                        className="border-input flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none"
                        value={bundleKeyId}
                        onChange={(e) => setBundleKeyId(e.target.value)}
                      >
                        {keys.map((k) => (
                          <option key={k.id} value={k.id}>
                            {k.name} ({k.keyPrefix})
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="int-secret">API key secret (paste once; not stored)</Label>
                      <Input
                        id="int-secret"
                        type="password"
                        autoComplete="off"
                        value={bundleSecret}
                        onChange={(e) => setBundleSecret(e.target.value)}
                        placeholder="Paste the secret shown when the key was created"
                      />
                    </div>
                    <Button type="button" onClick={handleDownloadClaude} disabled={downloading}>
                      {downloading ? (
                        <>
                          <Loader2 className="mr-2 size-4 animate-spin" />
                          Building…
                        </>
                      ) : (
                        'Download Claude bundle (zip)'
                      )}
                    </Button>
                  </>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>ChatGPT (Custom GPT / Actions)</CardTitle>
                <CardDescription>
                  Use the OpenAPI schema and tool invoke URL below. Authenticate with a Platform-issued API key (Bearer
                  or <code className="text-xs">X-API-Key</code>).
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div>
                  <p className="font-medium text-foreground">OpenAPI schema URL</p>
                  <p className="mt-1 break-all rounded-md bg-muted px-2 py-1.5 font-mono text-xs">
                    {ctx?.openapiUrl}
                  </p>
                </div>
                <div>
                  <p className="font-medium text-foreground">Invoke URL (POST)</p>
                  <p className="mt-1 break-all rounded-md bg-muted px-2 py-1.5 font-mono text-xs">
                    {ctx?.invokeUrl}
                  </p>
                </div>
                <p className="text-muted-foreground">
                  Create keys from Platform → API keys (superuser). Study-scoped keys must send{' '}
                  <code className="text-xs">study_id</code> in each tool&apos;s arguments.
                </p>
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  )
}
