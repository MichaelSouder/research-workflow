import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { getMcpApiKeys, getToolInvocations, purgeToolInvocationLogs } from '../api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { DateTimePicker } from '@/components/ui/datetime-picker'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
import { useAuth } from '../contexts/AuthContext'
import { Download, Loader2, Trash2 } from 'lucide-react'

const limit = 50

function statusRangeToParams(range) {
  if (!range) return {}
  if (range === '2xx') return { statusMin: 200, statusMax: 299 }
  if (range === '4xx') return { statusMin: 400, statusMax: 499 }
  if (range === '5xx') return { statusMin: 500, statusMax: 599 }
  if (range === 'err') return { statusMin: 400, statusMax: 599 }
  return {}
}

function csvEscape(s) {
  if (s == null) return ''
  const t = String(s)
  if (/[",\n\r]/.test(t)) return `"${t.replace(/"/g, '""')}"`
  return t
}

/** Local `YYYY-MM-DDTHH:mm` → ISO for API query params */
function localDateTimeToIso(local) {
  if (!local || !String(local).trim()) return null
  const d = new Date(local)
  if (Number.isNaN(d.getTime())) return null
  return d.toISOString()
}

export default function PlatformApiLogsPage() {
  const { isSuperuser } = useAuth()
  const [invocations, setInvocations] = useState([])
  const [total, setTotal] = useState(0)
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState(null)

  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [tool, setTool] = useState('')
  const [apiKeyId, setApiKeyId] = useState('')
  const [studyId, setStudyId] = useState('')
  const [statusRange, setStatusRange] = useState('')

  const [applied, setApplied] = useState({
    from: '',
    to: '',
    tool: '',
    apiKeyId: '',
    studyId: '',
    statusRange: '',
  })
  const [offset, setOffset] = useState(0)

  const [purgeOpen, setPurgeOpen] = useState(false)
  const [purgeDays, setPurgeDays] = useState(90)
  const [purging, setPurging] = useState(false)
  const [detailRow, setDetailRow] = useState(null)

  const loadKeys = useCallback(async () => {
    const r = await getMcpApiKeys()
    setKeys(r.keys || [])
  }, [])

  const runQuery = useCallback(
    async (opts = {}) => {
      setError(null)
      const off = opts.offset !== undefined ? opts.offset : offset
      const sr = statusRangeToParams(applied.statusRange)
      const res = await getToolInvocations({
        limit,
        offset: off,
        from: localDateTimeToIso(applied.from) ?? undefined,
        to: localDateTimeToIso(applied.to) ?? undefined,
        tool: applied.tool.trim() || undefined,
        apiKeyId: applied.apiKeyId.trim() || undefined,
        studyId: applied.studyId.trim() || undefined,
        ...sr,
      })
      setInvocations(res.invocations || [])
      setTotal(res.total ?? 0)
    },
    [offset, applied]
  )

  useEffect(() => {
    if (!isSuperuser) {
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        await loadKeys()
      } catch (e) {
        if (!cancelled) setError(e.message)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [isSuperuser, loadKeys])

  useEffect(() => {
    if (!isSuperuser) return
    let cancelled = false
    setLoading(true)
    ;(async () => {
      try {
        await runQuery()
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [isSuperuser, runQuery])

  const applyFilters = () => {
    setApplied({
      from,
      to,
      tool,
      apiKeyId,
      studyId,
      statusRange,
    })
    setOffset(0)
  }

  const clearFilters = () => {
    setFrom('')
    setTo('')
    setTool('')
    setApiKeyId('')
    setStudyId('')
    setStatusRange('')
    setApplied({
      from: '',
      to: '',
      tool: '',
      apiKeyId: '',
      studyId: '',
      statusRange: '',
    })
    setOffset(0)
  }

  const exportCsv = async () => {
    setExporting(true)
    try {
      const sr = statusRangeToParams(applied.statusRange)
      const res = await getToolInvocations({
        limit: 5000,
        offset: 0,
        from: localDateTimeToIso(applied.from) ?? undefined,
        to: localDateTimeToIso(applied.to) ?? undefined,
        tool: applied.tool.trim() || undefined,
        apiKeyId: applied.apiKeyId.trim() || undefined,
        studyId: applied.studyId.trim() || undefined,
        ...sr,
      })
      const rows = res.invocations || []
      const header = [
        'createdAt',
        'keySource',
        'keyPrefix',
        'toolName',
        'studyId',
        'statusCode',
        'durationMs',
        'errorDetail',
      ]
      const lines = [
        header.join(','),
        ...rows.map((r) =>
          [
            r.createdAt,
            r.keySource,
            r.keyPrefix,
            r.toolName,
            r.studyId,
            r.statusCode,
            r.durationMs,
            r.errorDetail,
          ]
            .map(csvEscape)
            .join(',')
        ),
      ]
      const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `tool-invocations-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(a.href)
      toast.success(`Exported ${rows.length} row(s)`)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setExporting(false)
    }
  }

  const runPurge = async () => {
    const d = Math.min(3650, Math.max(1, parseInt(String(purgeDays), 10) || 90))
    setPurging(true)
    try {
      const res = await purgeToolInvocationLogs(d)
      toast.success(`Removed ${res.removed} log row(s)`)
      setPurgeOpen(false)
      setOffset(0)
      await runQuery({ offset: 0 })
    } catch (e) {
      toast.error(e.message)
    } finally {
      setPurging(false)
    }
  }

  if (!isSuperuser) return null

  const page = Math.floor(offset / limit) + 1
  const totalPages = Math.max(1, Math.ceil(total / limit) || 1)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Tool API Audit Log</h2>
        <p className="text-sm text-muted-foreground">
          Entries for{' '}
          <code className="rounded border border-border bg-muted px-1 font-mono text-xs">POST /v1/tools/invoke</code>
          , including failed auth attempts. Metadata only (no request bodies).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
          <CardDescription>
            From / To use your local date and time (optional). Press Enter or click Apply to search.
          </CardDescription>
        </CardHeader>
        <form
          className="grid gap-4 px-6 sm:grid-cols-2 lg:grid-cols-3"
          onSubmit={(e) => {
            e.preventDefault()
            applyFilters()
          }}
        >
          <div className="grid gap-2">
            <Label htmlFor="log-from">From</Label>
            <DateTimePicker
              id="log-from"
              value={from}
              onChange={setFrom}
              allowClear
              placeholder="No start"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="log-to">To</Label>
            <DateTimePicker
              id="log-to"
              value={to}
              onChange={setTo}
              allowClear
              placeholder="No end"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="log-tool">Tool Name</Label>
            <Input id="log-tool" value={tool} onChange={(e) => setTool(e.target.value)} placeholder="qual_studies_list" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="log-study">Study ID</Label>
            <Input
              id="log-study"
              value={studyId}
              onChange={(e) => setStudyId(e.target.value)}
              placeholder="UUID"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="log-status">HTTP Status</Label>
            <select
              id="log-status"
              className="border-input flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none"
              value={statusRange}
              onChange={(e) => setStatusRange(e.target.value)}
            >
              <option value="">Any</option>
              <option value="2xx">2xx Success</option>
              <option value="err">4xx / 5xx Errors</option>
              <option value="4xx">4xx Only</option>
              <option value="5xx">5xx Only</option>
            </select>
          </div>
          <div className="grid gap-2 sm:col-span-2">
            <Label htmlFor="log-key">API Key</Label>
            <select
              id="log-key"
              className="border-input flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs outline-none"
              value={apiKeyId}
              onChange={(e) => setApiKeyId(e.target.value)}
            >
              <option value="">Any</option>
              {keys
                .filter((k) => !k.revokedAt)
                .map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.name} ({k.keyPrefix})
                  </option>
                ))}
            </select>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <Button type="submit">Apply</Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                clearFilters()
              }}
            >
              Clear
            </Button>
          </div>
        </form>
      </Card>

      {error ? <p className="text-destructive">{error}</p> : null}

      <Card className="overflow-hidden border-border shadow-sm">
        <CardHeader className="flex flex-col gap-3 border-b border-border bg-card">
          <div className="flex flex-row flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-lg">Invocations</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {total} total · page {page} / {totalPages}
              </span>
              <Button type="button" variant="outline" size="sm" disabled={exporting} onClick={exportCsv}>
                {exporting ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : (
                  <Download className="mr-2 size-4" />
                )}
                Export CSV
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={() => setPurgeOpen(true)}>
                <Trash2 className="mr-2 size-4" />
                Purge Old Logs
              </Button>
            </div>
          </div>
          <p className="text-muted-foreground text-xs">
            Typical retention is 30–90 days; purging permanently deletes rows older than the cutoff you choose.
          </p>
        </CardHeader>
        <CardContent className="pt-6">
          {loading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              Loading…
            </div>
          ) : invocations.length === 0 ? (
            <p className="text-muted-foreground py-8 text-center text-sm">
              No invocations match your filters. Adjust filters and click Apply.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-md border border-border">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableHead className="bg-card sticky left-0 z-10 min-w-[148px] border-r border-border">
                      Time
                    </TableHead>
                    <TableHead>Key</TableHead>
                    <TableHead>Tool</TableHead>
                    <TableHead>Study</TableHead>
                    <TableHead className="text-right">HTTP</TableHead>
                    <TableHead className="text-right">ms</TableHead>
                    <TableHead>Error</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invocations.map((row) => (
                    <TableRow
                      key={row.id}
                      className="hover:bg-muted/40 cursor-pointer"
                      onClick={() => setDetailRow(row)}
                    >
                      <TableCell className="bg-card sticky left-0 z-10 border-r border-border font-mono text-xs whitespace-nowrap">
                        {row.createdAt?.replace('T', ' ').slice(0, 19) ?? '—'}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        <span className="text-muted-foreground">{row.keySource}</span> {row.keyPrefix}
                      </TableCell>
                      <TableCell className="max-w-[180px] truncate font-mono text-xs">{row.toolName || '—'}</TableCell>
                      <TableCell className="max-w-[120px] truncate font-mono text-xs text-muted-foreground">
                        {row.studyId || '—'}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{row.statusCode}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.durationMs}</TableCell>
                      <TableCell className="max-w-[200px] truncate text-xs text-destructive">
                        {row.errorDetail || '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          <div className="mt-4 flex flex-wrap justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={offset < limit || loading}
              onClick={() => setOffset((o) => Math.max(0, o - limit))}
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={offset + limit >= total || loading}
              onClick={() => setOffset((o) => o + limit)}
            >
              Next
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={detailRow != null} onOpenChange={(o) => !o && setDetailRow(null)}>
        <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Invocation Detail</DialogTitle>
            <DialogDescription>
              Metadata only (no request bodies). Click a row in the table to open this view.
            </DialogDescription>
          </DialogHeader>
          {detailRow ? (
            <dl className="grid gap-3 text-sm">
              <div>
                <dt className="text-muted-foreground font-medium">ID</dt>
                <dd className="font-mono text-xs break-all">{detailRow.id}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground font-medium">Created</dt>
                <dd className="font-mono text-xs">{detailRow.createdAt ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground font-medium">API Key ID</dt>
                <dd className="font-mono text-xs break-all">{detailRow.apiKeyId ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground font-medium">Key</dt>
                <dd className="font-mono text-xs">
                  <span className="text-muted-foreground">{detailRow.keySource}</span> {detailRow.keyPrefix}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground font-medium">Tool</dt>
                <dd className="font-mono text-xs">{detailRow.toolName ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground font-medium">Study ID</dt>
                <dd className="font-mono text-xs break-all">{detailRow.studyId ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground font-medium">HTTP Status</dt>
                <dd>{detailRow.statusCode ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground font-medium">Duration (ms)</dt>
                <dd>{detailRow.durationMs ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground font-medium">Error Detail</dt>
                <dd className="text-destructive min-h-[1em] whitespace-pre-wrap break-words">
                  {detailRow.errorDetail || '—'}
                </dd>
              </div>
            </dl>
          ) : null}
        </DialogContent>
      </Dialog>

      <AlertDialog open={purgeOpen} onOpenChange={setPurgeOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Purge old audit logs?</AlertDialogTitle>
            <AlertDialogDescription>
              Permanently deletes rows older than the number of days below. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="grid gap-2 py-2">
            <Label htmlFor="purge-days">Older than (days)</Label>
            <Input
              id="purge-days"
              type="number"
              min={1}
              max={3650}
              value={purgeDays}
              onChange={(e) => setPurgeDays(e.target.value)}
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <Button type="button" variant="destructive" onClick={runPurge} disabled={purging}>
              {purging ? 'Purging…' : 'Purge'}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
