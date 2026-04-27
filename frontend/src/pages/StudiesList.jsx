import { useState, useEffect, useCallback, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getStudiesDashboard, createStudy } from '../api'
import { useAuth } from '../contexts/AuthContext'
import PageHeader from '../components/PageHeader'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { STATUS_LABELS } from '../constants'
import { Loader2, Plus } from 'lucide-react'

const DASHBOARD_POLL_MS = 15000

const statusVariant = (status) => {
  switch (status) {
    case 'running': return 'default'
    case 'failed': return 'destructive'
    default: return 'secondary'
  }
}

export default function StudiesList() {
  const navigate = useNavigate()
  const { user, isSuperuser } = useAuth()
  const [studies, setStudies] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [createName, setCreateName] = useState('')
  const [createDesc, setCreateDesc] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState(null)
  const pollRef = useRef(null)

  const fetchDashboard = useCallback(async () => {
    const data = await getStudiesDashboard()
    return data.studies || []
  }, [])

  useEffect(() => {
    if (!user) {
      setLoading(false)
      return
    }
    let cancelled = false
    fetchDashboard()
      .then((list) => {
        if (cancelled) return
        setStudies(list)
      })
      .catch((e) => {
        if (cancelled) return
        if (e?.message?.includes('401') || e?.message?.toLowerCase().includes('unauthorized')) {
          navigate('/login', { replace: true })
          return
        }
        setStudies([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [user, navigate, fetchDashboard])

  useEffect(() => {
    if (!user || studies.length === 0) return
    pollRef.current = setInterval(() => {
      if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return
      fetchDashboard().then((list) => setStudies(list))
    }, DASHBOARD_POLL_MS)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [user, studies.length, fetchDashboard])

  const canCreate = isSuperuser || studies.some((s) => s.roleCanonical === 'admin')

  const handleCreateStudy = async () => {
    if (!createName.trim()) return
    setCreating(true)
    setCreateError(null)
    try {
      const { study } = await createStudy({ name: createName.trim(), description: createDesc.trim() || undefined })
      setShowCreate(false)
      setCreateName('')
      setCreateDesc('')
      navigate(`/studies/${study.id}/admin`)
    } catch (e) {
      setCreateError(e.message)
    } finally {
      setCreating(false)
    }
  }

  const closeCreate = () => {
    setShowCreate(false)
    setCreateError(null)
    setCreateName('')
    setCreateDesc('')
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Loading dashboard…</p>
      </div>
    )
  }

  const studyCount = studies.length

  return (
    <div className="min-h-screen bg-muted/30 text-foreground">
      <main className="mx-auto max-w-6xl space-y-8 px-4 py-8 md:px-6 md:py-10">
        <PageHeader
          className="border-0 pb-0"
          title="Dashboard"
          description="Studies you can access, pipeline run status, and quick links. Data refreshes while this tab is open."
        />

        {studyCount === 0 && !showCreate ? (
          <Card className="border-border shadow-sm">
            <CardContent className="flex flex-col items-center justify-center gap-4 py-14 text-center">
              <div className="space-y-2">
                <p className="text-base font-medium text-foreground">No studies yet</p>
                <p className="max-w-md text-sm text-muted-foreground">
                  {canCreate
                    ? 'Create a study to get started, or ask another admin to add you to an existing one.'
                    : 'You don’t have access to any studies. Ask a study admin to invite you.'}
                </p>
              </div>
              {canCreate ? (
                <Button onClick={() => setShowCreate(true)} className="gap-2">
                  <Plus className="size-4" aria-hidden />
                  Create your first study
                </Button>
              ) : null}
            </CardContent>
          </Card>
        ) : null}

        {(studyCount > 0 || showCreate) ? (
          <Card className="overflow-hidden border-border shadow-sm">
            <CardHeader className="flex flex-col gap-4 space-y-0 border-b border-border bg-card pb-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                <CardTitle className="text-lg">Your Studies</CardTitle>
                <CardDescription>
                  {studyCount === 0
                    ? 'Add a study to see it listed here.'
                    : `${studyCount} ${studyCount === 1 ? 'study' : 'studies'} · Run status updates about every ${DASHBOARD_POLL_MS / 1000}s`}
                </CardDescription>
              </div>
              {canCreate ? (
                <Button
                  type="button"
                  variant={showCreate ? 'secondary' : 'outline'}
                  size="sm"
                  className="shrink-0 gap-1.5 sm:self-start"
                  onClick={() => (showCreate ? closeCreate() : setShowCreate(true))}
                >
                  {showCreate ? (
                    'Close form'
                  ) : (
                    <>
                      <Plus className="size-4" aria-hidden />
                      New Study
                    </>
                  )}
                </Button>
              ) : null}
            </CardHeader>

            {showCreate && canCreate ? (
              <div className="border-b border-border bg-muted/40 px-6 py-5">
                <p className="mb-4 text-sm font-medium text-foreground">Create a new study</p>
                <div className="grid max-w-xl gap-4 sm:grid-cols-1">
                  <div className="space-y-2">
                    <Label htmlFor="new-name">Name</Label>
                    <Input
                      id="new-name"
                      value={createName}
                      onChange={(e) => setCreateName(e.target.value)}
                      placeholder="e.g. Q1 customer survey"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="new-desc">Description <span className="font-normal text-muted-foreground">(optional)</span></Label>
                    <Input
                      id="new-desc"
                      value={createDesc}
                      onChange={(e) => setCreateDesc(e.target.value)}
                      placeholder="Short note for your team"
                    />
                  </div>
                  {createError ? <p className="text-sm text-destructive">{createError}</p> : null}
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={handleCreateStudy} disabled={creating || !createName.trim()}>
                      {creating ? 'Creating…' : 'Create Study'}
                    </Button>
                    <Button type="button" variant="ghost" onClick={closeCreate} disabled={creating}>
                      Cancel
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}

            {studyCount > 0 ? (
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <Table className="min-w-[720px]">
                    <TableCaption id="dashboard-table-caption" className="sr-only">
                      Your studies and pipelines
                    </TableCaption>
                    <TableHeader>
                      <TableRow className="border-b border-border bg-muted/20 hover:bg-muted/20">
                        <TableHead scope="col" className="pl-6">Study</TableHead>
                        <TableHead scope="col" className="w-[100px]">Role</TableHead>
                        <TableHead scope="col" className="w-[130px]">Run Status</TableHead>
                        <TableHead scope="col">Pipelines</TableHead>
                        <TableHead scope="col" className="w-[200px] pr-6 text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {studies.map((s) => {
                        const runStatus = s.status?.status ?? 'idle'
                        const pipelines = s.pipelines ?? []
                        return (
                          <TableRow key={s.id} className="border-border/80">
                            <TableCell className="pl-6 align-top">
                              <div className="font-medium text-foreground">{s.name}</div>
                              {s.description ? (
                                <div className="mt-0.5 max-w-md text-sm text-muted-foreground line-clamp-2">{s.description}</div>
                              ) : null}
                            </TableCell>
                            <TableCell className="align-top">
                              <Badge variant="secondary" className="capitalize">
                                {s.role}
                              </Badge>
                            </TableCell>
                            <TableCell className="align-top">
                              <Badge variant={statusVariant(runStatus)} className="gap-1">
                                {runStatus === 'running' && <Loader2 className="size-3 animate-spin" aria-hidden />}
                                {STATUS_LABELS[runStatus] ?? runStatus}
                              </Badge>
                            </TableCell>
                            <TableCell className="align-top text-sm text-muted-foreground">
                              {pipelines.length === 0 ? (
                                '—'
                              ) : (
                                <ul className="flex flex-col gap-1.5">
                                  {pipelines.map((p) => (
                                    <li key={p.id} className="flex flex-wrap items-center gap-1.5">
                                      <span>{p.name}</span>
                                      {p.isDefault ? (
                                        <Badge variant="outline" className="text-xs font-normal">Default</Badge>
                                      ) : null}
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </TableCell>
                            <TableCell className="pr-6 text-right align-top">
                              <div className="flex flex-wrap justify-end gap-2">
                                <Button variant="default" size="sm" asChild>
                                  <Link to={`/studies/${s.id}`}>Open</Link>
                                </Button>
                                <Button variant="outline" size="sm" asChild>
                                  <Link to={`/studies/${s.id}/pipeline-graph`}>Graph</Link>
                                </Button>
                                {(s.roleCanonical === 'admin' || isSuperuser) && (
                                  <Button variant="outline" size="sm" asChild>
                                    <Link to={`/studies/${s.id}/admin`}>Admin</Link>
                                  </Button>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            ) : showCreate ? (
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                After you create a study, it will appear in this list.
              </CardContent>
            ) : null}
          </Card>
        ) : null}
      </main>
    </div>
  )
}
