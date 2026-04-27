import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import {
  createMcpApiKey,
  getMcpApiKeys,
  getMcpToolNames,
  getPlatformUsers,
  getStudies,
  patchMcpApiKey,
  revokeMcpApiKey,
  rotateMcpApiKey,
} from '../api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { useAuth } from '../contexts/AuthContext'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import { DateTimePicker } from '@/components/ui/datetime-picker'

function localDateTimeToIso(local) {
  if (!local || !local.trim()) return null
  const d = new Date(local)
  if (Number.isNaN(d.getTime())) return null
  return d.toISOString()
}

export default function PlatformApiKeysPage() {
  const { isSuperuser, user: authUser } = useAuth()
  const [keys, setKeys] = useState([])
  const [tools, setTools] = useState([])
  const [platformUsers, setPlatformUsers] = useState([])
  const [studies, setStudies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('API key')
  const [createExpires, setCreateExpires] = useState('')
  const [ownerUserId, setOwnerUserId] = useState('')
  const [scopes, setScopes] = useState(() => new Set())
  const [createStudyAllow, setCreateStudyAllow] = useState(() => new Set())
  const [newSecret, setNewSecret] = useState(null)
  const [revokeId, setRevokeId] = useState(null)
  const [pendingRevoke, setPendingRevoke] = useState(false)
  const [rotateId, setRotateId] = useState(null)
  const [pendingRotate, setPendingRotate] = useState(false)

  const [editOpen, setEditOpen] = useState(false)
  const [editKey, setEditKey] = useState(null)
  const [editName, setEditName] = useState('')
  const [editExpires, setEditExpires] = useState('')
  const [editOwnerUserId, setEditOwnerUserId] = useState('')
  const [editStudyAllow, setEditStudyAllow] = useState(() => new Set())
  const [savingEdit, setSavingEdit] = useState(false)

  const userById = useMemo(() => {
    const m = new Map()
    for (const u of platformUsers) m.set(u.id, u)
    return m
  }, [platformUsers])

  const studyById = useMemo(() => {
    const m = new Map()
    for (const s of studies) m.set(s.id, s)
    return m
  }, [studies])

  const load = useCallback(async () => {
    const settled = await Promise.allSettled([
      getMcpApiKeys(),
      getMcpToolNames(),
      getPlatformUsers(),
      getStudies(),
    ])
    const msgs = []
    if (settled[0].status === 'fulfilled') {
      setKeys(settled[0].value.keys || [])
      setError(null)
    } else {
      const m = settled[0].reason?.message || 'Failed to load keys'
      msgs.push(`Keys: ${m}`)
      setError(m)
    }
    if (settled[1].status === 'fulfilled') {
      setTools(settled[1].value.tools || [])
    } else {
      msgs.push(`Tool names: ${settled[1].reason?.message || 'failed'}`)
    }
    if (settled[2].status === 'fulfilled') {
      setPlatformUsers(settled[2].value.users || [])
    } else {
      msgs.push(`Users: ${settled[2].reason?.message || 'failed'}`)
    }
    if (settled[3].status === 'fulfilled') {
      setStudies(settled[3].value.studies || [])
    } else {
      msgs.push(`Studies: ${settled[3].reason?.message || 'failed'}`)
    }
    if (msgs.length) toast.error(msgs.join(' · '))
  }, [])

  useEffect(() => {
    if (!isSuperuser) {
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        await load()
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [isSuperuser, load])

  useEffect(() => {
    if (!authUser?.id || ownerUserId) return
    if (!platformUsers.some((u) => u.id === authUser.id)) return
    setOwnerUserId(authUser.id)
  }, [authUser?.id, ownerUserId, platformUsers])

  const toggleScope = (t) => {
    setScopes((prev) => {
      const next = new Set(prev)
      if (next.has(t)) next.delete(t)
      else next.add(t)
      return next
    })
  }

  const selectAllTools = () => setScopes(new Set(tools))
  const clearScopes = () => setScopes(new Set())

  const toggleCreateStudy = (studyId) => {
    setCreateStudyAllow((prev) => {
      const next = new Set(prev)
      if (next.has(studyId)) next.delete(studyId)
      else next.add(studyId)
      return next
    })
  }

  const toggleEditStudy = (studyId) => {
    setEditStudyAllow((prev) => {
      const next = new Set(prev)
      if (next.has(studyId)) next.delete(studyId)
      else next.add(studyId)
      return next
    })
  }

  const onCreate = async () => {
    if (!ownerUserId?.trim()) {
      toast.error('Select an owner for this key.')
      return
    }
    if (createStudyAllow.size === 0) {
      toast.error('Select at least one study.')
      return
    }
    const expIso = localDateTimeToIso(createExpires)
    if (!expIso) {
      toast.error('Set an expiry date and time for this key.')
      return
    }
    setCreating(true)
    setError(null)
    try {
      const scopeList = scopes.size > 0 ? [...scopes].sort() : []
      const allowIds = [...createStudyAllow].sort()
      const res = await createMcpApiKey({
        name: name.trim() || 'API key',
        scopes: scopeList,
        ownerUserId: ownerUserId.trim(),
        expiresAt: expIso,
        allowedStudyIds: allowIds,
      })
      setNewSecret(res.secret)
      setName('API key')
      setCreateExpires('')
      setOwnerUserId('')
      setScopes(new Set())
      setCreateStudyAllow(new Set())
      await load()
      toast.success('API key created')
    } catch (e) {
      setError(e.message)
      toast.error(e.message)
    } finally {
      setCreating(false)
    }
  }

  const copySecret = async () => {
    if (!newSecret) return
    try {
      await navigator.clipboard.writeText(newSecret)
      toast.success('Copied to clipboard')
    } catch {
      toast.error('Could not copy')
    }
  }

  const confirmRevoke = async () => {
    if (!revokeId) return
    setPendingRevoke(true)
    try {
      await revokeMcpApiKey(revokeId)
      await load()
      toast.success('Key revoked')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setPendingRevoke(false)
      setRevokeId(null)
    }
  }

  const openEdit = (k) => {
    setEditKey(k)
    setEditOwnerUserId((k.ownerUserId || authUser?.id || '').trim())
    setEditName(k.name || '')
    if (k.expiresAt) {
      try {
        const d = new Date(k.expiresAt)
        const pad = (n) => String(n).padStart(2, '0')
        setEditExpires(
          `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
        )
      } catch {
        setEditExpires('')
      }
    } else {
      setEditExpires('')
    }
    setEditStudyAllow(new Set(k.allowedStudyIds || []))
    setEditOpen(true)
  }

  const saveEdit = async () => {
    if (!editKey) return
    if (!editOwnerUserId?.trim()) {
      toast.error('Select an owner for this key.')
      return
    }
    if (editStudyAllow.size === 0) {
      toast.error('Select at least one study.')
      return
    }
    const iso = localDateTimeToIso(editExpires)
    if (!iso) {
      toast.error('Set an expiry date and time for this key.')
      return
    }
    setSavingEdit(true)
    try {
      const nm = editName.trim() || 'API key'
      const patch = { name: nm, expiresAt: iso, ownerUserId: editOwnerUserId.trim() }
      const prevAllow = [...(editKey.allowedStudyIds || [])].sort()
      const nextAllow = [...editStudyAllow].sort()
      const allowChanged =
        prevAllow.length !== nextAllow.length || prevAllow.some((id, i) => id !== nextAllow[i])
      if (allowChanged) {
        patch.allowedStudyIds = nextAllow
      }
      await patchMcpApiKey(editKey.id, patch)
      await load()
      toast.success('Key updated')
      setEditOpen(false)
      setEditKey(null)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSavingEdit(false)
    }
  }

  const confirmRotate = async () => {
    if (!rotateId) return
    setPendingRotate(true)
    try {
      const res = await rotateMcpApiKey(rotateId)
      setNewSecret(res.secret)
      await load()
      toast.success('Key rotated — copy the new secret')
      setRotateId(null)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setPendingRotate(false)
    }
  }

  if (!isSuperuser) return null

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="h-4 w-full max-w-xl" />
        </div>
        <div className="space-y-3 rounded-lg border border-border p-6">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-32 w-full" />
        </div>
        <div className="space-y-3 rounded-lg border border-border p-6">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">MCP and Tool API Keys</h2>
        <p className="text-sm text-muted-foreground">
          Use these bearer tokens for{' '}
          <code className="rounded border border-border bg-muted px-1 font-mono text-xs">
            POST /v1/tools/invoke
          </code>
          . Each key must have an owner and at least one study; every tool call must include{' '}
          <code className="font-mono text-xs">study_id</code> in <code className="font-mono text-xs">arguments</code>.
          Empty tool scope means all tools. The full secret is shown only once when you create or rotate — the server
          stores a hash, not the token. Env keys (
          <code className="font-mono text-xs">MCP_API_KEY</code>) are global and appear as{' '}
          <code className="font-mono text-xs">env</code> in logs.
        </p>
      </div>

      {newSecret ? (
        <Card className="border-amber-500/50 bg-amber-500/5">
          <CardHeader>
            <CardTitle className="text-base text-amber-900 dark:text-amber-100">
              Copy your new secret
            </CardTitle>
            <CardDescription>
              This is the only time the full token is shown. Store it in a password manager.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <pre className="overflow-x-auto rounded-md border border-border bg-muted p-3 text-xs break-all">
              {newSecret}
            </pre>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" onClick={copySecret}>
                Copy
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => setNewSecret(null)}>
                Dismiss
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card className="border-border shadow-sm">
        <CardHeader>
          <CardTitle className="text-lg">Create Key</CardTitle>
          <CardDescription>
            Optional scopes restrict which tool names can be invoked. Owner, expiry, and at least one study are required.
            Owner defaults to you so the key appears on Integrations for the Claude MCP zip.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="key-name">Name</Label>
              <Input
                id="key-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. ChatGPT connector"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="key-owner">Owner (required)</Label>
              <select
                id="key-owner"
                className="border-input flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none"
                value={ownerUserId}
                onChange={(e) => setOwnerUserId(e.target.value)}
                required
              >
                <option value="">— Select user —</option>
                {platformUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} ({u.email}) · {u.id.slice(0, 8)}…
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2 sm:col-span-2">
              <Label htmlFor="key-exp">Expires (required, local time)</Label>
              <DateTimePicker
                id="key-exp"
                value={createExpires}
                onChange={setCreateExpires}
                allowClear={false}
                placeholder="Pick date and time"
              />
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" size="sm" onClick={selectAllTools}>
                Select all tools
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={clearScopes}>
                Clear (full access)
              </Button>
            </div>
            <div
              className="max-h-52 space-y-2 overflow-y-auto rounded-md border border-border p-3"
              role="group"
              aria-label="Tool scopes"
            >
              {tools.map((t) => (
                <label key={t} className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={scopes.has(t)}
                    onChange={() => toggleScope(t)}
                    className="size-4 rounded border-border"
                  />
                  <span className="font-mono text-xs">{t}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium">Studies (required)</p>
            <p className="text-muted-foreground text-xs">
              Select one or more studies this key may access. Tool calls must pass a matching{' '}
              <code className="font-mono text-xs">study_id</code>.
            </p>
            <div
              className="max-h-40 space-y-2 overflow-y-auto rounded-md border border-border p-3"
              role="group"
              aria-label="Study allowlist"
            >
              {studies.length === 0 ? (
                <p className="text-muted-foreground text-xs">No studies loaded.</p>
              ) : (
                studies.map((s) => (
                  <label key={s.id} className="flex cursor-pointer items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={createStudyAllow.has(s.id)}
                      onChange={() => toggleCreateStudy(s.id)}
                      className="size-4 rounded border-border"
                    />
                    <span>{s.name}</span>
                    <span className="text-muted-foreground font-mono text-xs">{s.id.slice(0, 8)}…</span>
                  </label>
                ))
              )}
            </div>
          </div>
          <Button type="button" onClick={onCreate} disabled={creating}>
            {creating ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Creating…
              </>
            ) : (
              'Create Key'
            )}
          </Button>
        </CardContent>
      </Card>

      <Card className="overflow-hidden border-border shadow-sm">
        <CardHeader className="border-b border-border bg-card">
          <CardTitle className="text-lg">API Keys</CardTitle>
        </CardHeader>
        <CardContent className="pt-6">
          {keys.length === 0 ? (
            <p className="text-muted-foreground py-6 text-center text-sm">
              No API keys yet. Create one above.
            </p>
          ) : (
          <div className="overflow-x-auto rounded-md border border-border">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/30 hover:bg-muted/30">
                  <TableHead>Name</TableHead>
                  <TableHead>Prefix</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead>Last Used</TableHead>
                  <TableHead>Scopes</TableHead>
                  <TableHead>Studies</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="min-w-[200px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {keys.map((k) => (
                  <TableRow key={k.id}>
                    <TableCell className="font-medium">{k.name}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{k.keyPrefix}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {k.ownerUserId ? (
                        <span>
                          {userById.get(k.ownerUserId)?.email || '—'} ·{' '}
                          <span className="font-mono text-[11px] text-foreground">{k.ownerUserId.slice(0, 8)}…</span>
                        </span>
                      ) : (
                        <span className="text-amber-700 dark:text-amber-300">Legacy — replace key</span>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                      {k.createdAt
                        ? new Date(k.createdAt).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
                        : '—'}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                      {k.expiresAt
                        ? new Date(k.expiresAt).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
                        : '—'}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                      {k.lastUsedAt
                        ? new Date(k.lastUsedAt).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
                        : '—'}
                    </TableCell>
                    <TableCell className="max-w-[160px] text-xs text-muted-foreground">
                      {!k.scopes?.length ? (
                        <span>All tools</span>
                      ) : (
                        <span className="line-clamp-2">{k.scopes.join(', ')}</span>
                      )}
                    </TableCell>
                    <TableCell className="max-w-[140px] text-xs text-muted-foreground">
                      {!k.allowedStudyIds?.length ? (
                        <span className="text-amber-700 dark:text-amber-300">Legacy — replace key</span>
                      ) : (
                        <span className="line-clamp-2">
                          {k.allowedStudyIds
                            .map((id) => studyById.get(id)?.name || id)
                            .join(', ')}
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      {k.revokedAt ? (
                        <Badge variant="secondary">Revoked</Badge>
                      ) : (
                        <Badge>Active</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className={cn(k.revokedAt && 'invisible')}
                          disabled={!!k.revokedAt}
                          onClick={() => openEdit(k)}
                        >
                          Edit
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className={cn(k.revokedAt && 'invisible')}
                          disabled={!!k.revokedAt}
                          onClick={() => setRotateId(k.id)}
                        >
                          Rotate
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className={cn(k.revokedAt && 'invisible')}
                          disabled={!!k.revokedAt}
                          onClick={() => setRevokeId(k.id)}
                        >
                          Revoke
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={!!revokeId} onOpenChange={(o) => !o && setRevokeId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revoke API Key?</AlertDialogTitle>
            <AlertDialogDescription>
              Clients using this token will receive 401. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <Button type="button" onClick={confirmRevoke} disabled={pendingRevoke}>
              {pendingRevoke ? 'Revoking…' : 'Revoke'}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!rotateId} onOpenChange={(o) => !o && setRotateId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rotate API Key?</AlertDialogTitle>
            <AlertDialogDescription>
              The current key will be revoked immediately. You will receive one new secret to copy. The key must have an
              expiry set; edit the key first if it does not.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <Button type="button" onClick={confirmRotate} disabled={pendingRotate}>
              {pendingRotate ? 'Rotating…' : 'Rotate'}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={editOpen} onOpenChange={(o) => !o && (setEditOpen(false), setEditKey(null))}>
        <AlertDialogContent className="max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle>Edit API Key</AlertDialogTitle>
            <AlertDialogDescription>
              Update the label, owner, expiry, or study allowlist. Only the key owner sees it on Integrations for the
              Claude bundle download.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="grid max-h-[min(70vh,520px)] gap-3 overflow-y-auto py-2">
            <div className="grid gap-2">
              <Label htmlFor="edit-name">Name</Label>
              <Input id="edit-name" value={editName} onChange={(e) => setEditName(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-owner">Owner</Label>
              <select
                id="edit-owner"
                className="border-input flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none"
                value={editOwnerUserId}
                onChange={(e) => setEditOwnerUserId(e.target.value)}
              >
                <option value="">— Select user —</option>
                {platformUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} ({u.email}) · {u.id.slice(0, 8)}…
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-exp">Expires (required, local time)</Label>
              <DateTimePicker
                id="edit-exp"
                value={editExpires}
                onChange={setEditExpires}
                allowClear={false}
                placeholder="Pick date and time"
              />
            </div>
            <div className="space-y-2">
              <Label>Studies</Label>
              <p className="text-muted-foreground text-xs">Keep at least one study selected.</p>
              <div className="max-h-36 space-y-2 overflow-y-auto rounded-md border border-border p-2">
                {studies.map((s) => (
                  <label key={s.id} className="flex cursor-pointer items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={editStudyAllow.has(s.id)}
                      onChange={() => toggleEditStudy(s.id)}
                      className="size-4 rounded border-border"
                    />
                    <span>{s.name}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <Button type="button" onClick={saveEdit} disabled={savingEdit}>
              {savingEdit ? 'Saving…' : 'Save'}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
