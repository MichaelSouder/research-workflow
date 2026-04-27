import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { getPlatformUser, patchPlatformUser, putPlatformUserStudies, getStudies } from '../api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAuth } from '../contexts/AuthContext'
import { Loader2, Trash2 } from 'lucide-react'

const ROLE_OPTIONS = [
  { value: 'staff', label: 'Staff' },
  { value: 'admin', label: 'Admin' },
]

/** Backend canonical role → form value (matches Study Admin page). */
function canonicalToSelectRole(canonical) {
  if (canonical === 'admin') return 'admin'
  return 'staff'
}

export default function PlatformUserDetailPage() {
  const { userId } = useParams()
  const { isSuperuser } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [allStudies, setAllStudies] = useState([])
  const [rows, setRows] = useState([])
  const [snapshot, setSnapshot] = useState([])
  const [addStudyId, setAddStudyId] = useState('')
  const [addRole, setAddRole] = useState('staff')
  const [saving, setSaving] = useState(false)
  const [proxySaving, setProxySaving] = useState(false)

  const load = useCallback(async () => {
    if (!isSuperuser || !userId) return
    const [userRes, studiesRes] = await Promise.all([getPlatformUser(userId), getStudies()])
    setData(userRes)
    setAllStudies(studiesRes.studies || [])
    const next = (userRes.studies || []).map((s) => ({
      studyId: s.studyId,
      name: s.name,
      roleSelect: canonicalToSelectRole(s.role),
    }))
    setRows(next)
    setSnapshot(next.map((r) => ({ studyId: r.studyId, roleSelect: r.roleSelect })))
  }, [isSuperuser, userId])

  useEffect(() => {
    if (!isSuperuser || !userId) {
      setLoading(false)
      return
    }
    let cancelled = false
    setError(null)
    setLoading(true)
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
  }, [isSuperuser, userId, load])

  const dirty = useMemo(() => {
    if (rows.length !== snapshot.length) return true
    const a = new Map(snapshot.map((r) => [r.studyId, r.roleSelect]))
    return rows.some((r) => a.get(r.studyId) !== r.roleSelect)
  }, [rows, snapshot])

  const studiesAvailableToAdd = useMemo(() => {
    const have = new Set(rows.map((r) => r.studyId))
    return allStudies.filter((s) => !have.has(s.id))
  }, [allStudies, rows])

  const handleRoleChange = (studyId, roleSelect) => {
    setRows((prev) => prev.map((r) => (r.studyId === studyId ? { ...r, roleSelect } : r)))
  }

  const handleRemove = (studyId) => {
    setRows((prev) => prev.filter((r) => r.studyId !== studyId))
  }

  const handleAddAccess = () => {
    if (!addStudyId) {
      toast.error('Choose a study.')
      return
    }
    const s = allStudies.find((x) => x.id === addStudyId)
    if (!s) return
    if (rows.some((r) => r.studyId === addStudyId)) return
    setRows((prev) => [
      ...prev,
      { studyId: s.id, name: s.name, roleSelect: addRole },
    ])
    setAddStudyId('')
    setAddRole('staff')
  }

  const handleDiscard = () => {
    setRows(
      snapshot.map((s) => {
        const name =
          allStudies.find((x) => x.id === s.studyId)?.name ||
          data?.studies?.find((x) => x.studyId === s.studyId)?.name ||
          s.studyId
        return { studyId: s.studyId, name, roleSelect: s.roleSelect }
      }),
    )
  }

  const handleSave = async () => {
    if (!userId || saving) return
    setSaving(true)
    try {
      const res = await putPlatformUserStudies(
        userId,
        rows.map((r) => ({ study_id: r.studyId, role: r.roleSelect })),
      )
      const next = (res.studies || []).map((s) => ({
        studyId: s.studyId,
        name: s.name,
        roleSelect: canonicalToSelectRole(s.role),
      }))
      setRows(next)
      setSnapshot(next.map((r) => ({ studyId: r.studyId, roleSelect: r.roleSelect })))
      setData((d) => (d ? { ...d, studies: res.studies } : d))
      toast.success('Study access updated.')
    } catch (e) {
      toast.error(e.message || 'Could not save.')
    } finally {
      setSaving(false)
    }
  }

  if (!isSuperuser) return null

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
        Loading user…
      </div>
    )
  }

  if (error) {
    return <p className="text-destructive">{error}</p>
  }

  const u = data?.user

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          to="/platform/users"
          className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          ← Users
        </Link>
      </div>
      <div>
        <h2 className="text-lg font-semibold">{u?.name || 'User'}</h2>
        <p className="text-sm text-muted-foreground">{u?.email}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {u?.isSuperuser ? (
            <Badge>Superuser</Badge>
          ) : (
            <Badge variant="secondary">Not a Superuser</Badge>
          )}
          {u?.hasPassword ? (
            <Badge variant="outline">Password Login Enabled</Badge>
          ) : (
            <Badge variant="secondary">No Password (Google Only)</Badge>
          )}
        </div>
      </div>
      <Card className="overflow-hidden border-border shadow-sm">
        <CardHeader className="border-b border-border bg-card">
          <CardTitle className="text-lg">Tool API data proxy</CardTitle>
          <CardDescription>
            When enabled, ChatGPT and other HTTP tool clients see masked (mock) data for sensitive reads. Applies to
            API keys owned by this user. Disabled only if you need a break-glass exception.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-6">
          <label className="flex cursor-pointer items-start gap-3 text-sm">
            <input
              type="checkbox"
              className="mt-1 size-4 rounded border border-input"
              checked={u?.toolApiDataProxy !== false}
              disabled={proxySaving}
              onChange={async (e) => {
                const checked = e.target.checked
                setProxySaving(true)
                try {
                  const res = await patchPlatformUser(userId, { tool_api_data_proxy: checked })
                  setData((d) =>
                    d && res.user ? { ...d, user: { ...d.user, ...res.user } } : d,
                  )
                  toast.success(checked ? 'Data proxy enabled.' : 'Data proxy disabled.')
                } catch (err) {
                  toast.error(err.message || 'Could not update setting.')
                } finally {
                  setProxySaving(false)
                }
              }}
            />
            <span>
              <span className="font-medium text-foreground">Mask sensitive tool responses</span>
              <span className="mt-1 block text-muted-foreground">
                Recommended on. Changes apply on the next tool call; no client reinstall required.
              </span>
            </span>
          </label>
        </CardContent>
      </Card>
      <Card className="overflow-hidden border-border shadow-sm">
        <CardHeader className="border-b border-border bg-card">
          <CardTitle className="text-lg">Study Access</CardTitle>
          <CardDescription>
            Set which studies this user can open and their role on each study (Staff or Admin). Each study must keep at
            least one admin—assign another admin on a study before removing the last admin there.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 pt-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
            <div className="grid gap-2 min-w-[200px] flex-1">
              <span className="text-sm font-medium">Add Study</span>
              <Select value={addStudyId || undefined} onValueChange={setAddStudyId}>
                <SelectTrigger>
                  <SelectValue placeholder={studiesAvailableToAdd.length ? 'Choose a Study…' : 'All Studies Assigned'} />
                </SelectTrigger>
                <SelectContent>
                  {studiesAvailableToAdd.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2 w-[140px]">
              <span className="text-sm font-medium">Role</span>
              <Select value={addRole} onValueChange={setAddRole}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLE_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="button" variant="secondary" onClick={handleAddAccess} disabled={!studiesAvailableToAdd.length}>
              Add Access
            </Button>
          </div>

          {!rows.length ? (
            <p className="text-sm text-muted-foreground">No study memberships yet. Add a study above.</p>
          ) : (
            <div className="rounded-md border border-border">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableHead scope="col">Study</TableHead>
                    <TableHead scope="col" className="min-w-[160px]">
                      Role
                    </TableHead>
                    <TableHead scope="col" className="w-[100px] text-right">
                      Remove
                    </TableHead>
                    <TableHead scope="col" className="w-[100px]">
                      Open
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow key={row.studyId}>
                      <TableCell className="font-medium">{row.name}</TableCell>
                      <TableCell>
                        <Select
                          value={row.roleSelect}
                          onValueChange={(v) => handleRoleChange(row.studyId, v)}
                        >
                          <SelectTrigger className="w-full max-w-[200px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {ROLE_OPTIONS.map((o) => (
                              <SelectItem key={o.value} value={o.value}>
                                {o.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="text-muted-foreground hover:text-destructive"
                          onClick={() => handleRemove(row.studyId)}
                          aria-label={`Remove access to ${row.name}`}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </TableCell>
                      <TableCell>
                        <Link
                          to={`/studies/${encodeURIComponent(row.studyId)}`}
                          className="text-sm text-primary underline-offset-4 hover:underline"
                        >
                          Dashboard
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={handleSave} disabled={!dirty || saving}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  Saving…
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
            <Button type="button" variant="outline" onClick={handleDiscard} disabled={!dirty || saving}>
              Discard
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
