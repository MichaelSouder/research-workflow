import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import {
  getStudies,
  getStudyStatus,
  getStudyConfig,
  saveStudyConfig,
  getStudyDistributionContacts,
  getStudyDistributionCheck,
  getStudyDistributionStatus,
  getStudyDistributionDistributions,
  getStudyDistributionSendPreview,
  postStudyDistributionSend,
  postStudyDistributionDeleteUnsent,
  postStudyDistributionExport,
  patchStudyDistributionContact,
} from '../api'
import { canEditStudy } from '../lib/roles'
import { useAuth } from '../contexts/AuthContext'
import { POLL_INTERVAL_MS, DISTRIBUTION_CONFIG_KEYS, DISTRIBUTION_CONFIG_LABELS, DISTRIBUTION_CONTACT_METHODS } from '../constants'
import Header from '../components/Header'
import Breadcrumb from '../components/Breadcrumb'
import PageHeader from '../components/PageHeader'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ArrowLeft, CheckCircle2, XCircle, FileDown, ListFilter, Send, Pencil, Check, X, Sliders } from 'lucide-react'

export default function DistributionPage() {
  const { studyId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [studies, setStudies] = useState([])
  const [status, setStatus] = useState(null)
  const [contacts, setContacts] = useState([])
  const [checkResult, setCheckResult] = useState(null)
  const [distStatus, setDistStatus] = useState({ busy: false, lastResult: null })
  const [loading, setLoading] = useState(true)
  const [loadingContacts, setLoadingContacts] = useState(false)
  const [checking, setChecking] = useState(false)
  const [sending, setSending] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [currentStudyRoleCanonical, setCurrentStudyRoleCanonical] = useState(null)
  const [deleteIndex, setDeleteIndex] = useState('')
  const [deleteContactId, setDeleteContactId] = useState('')
  const [deleteAllUnsent, setDeleteAllUnsent] = useState(false)
  const [previewResult, setPreviewResult] = useState(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [distributionsList, setDistributionsList] = useState({ email: [], sms: [], errors: [] })
  const [loadingDistributions, setLoadingDistributions] = useState(false)
  const [sendLimit, setSendLimit] = useState('')
  const [sendIndices, setSendIndices] = useState('')
  const [bypassTimeSlot, setBypassTimeSlot] = useState(false)
  const [exportLoading, setExportLoading] = useState(false)
  const [exportResult, setExportResult] = useState(null)
  const [editingContactId, setEditingContactId] = useState(null)
  const [editDraft, setEditDraft] = useState(null)
  const [distConfigForm, setDistConfigForm] = useState({})
  const [distConfigSaving, setDistConfigSaving] = useState(false)

  const canEdit = canEditStudy(currentStudyRoleCanonical)
  const studyName = studies.find((s) => s.id === studyId)?.name || 'Study'

  useEffect(() => {
    if (!user) return
    let cancelled = false
    getStudies()
      .then((data) => {
        if (!cancelled) setStudies(data.studies || [])
      })
      .catch(() => {
        if (!cancelled) setStudies([])
      })
    return () => { cancelled = true }
  }, [user])

  const fetchStatus = useCallback(async () => {
    if (!studyId) return
    try {
      const s = await getStudyStatus(studyId)
      setStatus(s.status)
      return s.status
    } catch (e) {
      if (e?.message?.includes('401') || e?.message?.includes('Not authenticated')) {
        navigate('/login', { replace: true })
        return null
      }
      if (e?.message?.includes('403') || e?.message?.includes('404')) {
        navigate('/studies', { replace: true })
        return null
      }
      return null
    }
  }, [navigate, studyId])

  const fetchContacts = useCallback(async () => {
    if (!studyId) return
    setLoadingContacts(true)
    setError(null)
    try {
      const res = await getStudyDistributionContacts(studyId)
      setContacts(res.contacts || [])
    } catch (e) {
      setError(e.message)
      setContacts([])
    } finally {
      setLoadingContacts(false)
    }
  }, [studyId])

  const fetchDistStatus = useCallback(async () => {
    if (!studyId) return
    try {
      const res = await getStudyDistributionStatus(studyId)
      setDistStatus({ busy: res.busy, lastResult: res.lastResult })
    } catch (_) {}
  }, [studyId])

  const fetchDistributions = useCallback(async () => {
    if (!studyId) return
    setLoadingDistributions(true)
    try {
      const res = await getStudyDistributionDistributions(studyId)
      setDistributionsList({
        email: res.email || [],
        sms: res.sms || [],
        errors: res.errors || [],
      })
    } catch (_) {
      setDistributionsList({ email: [], sms: [], errors: [] })
    } finally {
      setLoadingDistributions(false)
    }
  }, [studyId])

  const fetchDistConfig = useCallback(async () => {
    if (!studyId) return
    try {
      const res = await getStudyConfig(studyId)
      const config = res?.config || {}
      const next = {}
      DISTRIBUTION_CONFIG_KEYS.forEach((k) => {
        next[k] = config[k] ?? ''
      })
      setDistConfigForm(next)
    } catch (_) {
      setDistConfigForm({})
    }
  }, [studyId])

  useEffect(() => {
    if (!user || !studyId) return
    const roleStudy = studies.find((s) => s.id === studyId)
    if (roleStudy) setCurrentStudyRoleCanonical(roleStudy.roleCanonical)
  }, [user, studyId, studies])

  useEffect(() => {
    if (!user || !studyId) return
    let cancelled = false
    const timeout = setTimeout(() => {
      if (cancelled) return
      setLoading(false)
    }, 3000)
    ;(async () => {
      try {
        await fetchStatus()
        await fetchContacts()
        await fetchDistStatus()
        await fetchDistributions()
        await fetchDistConfig()
      } catch (_) {}
      if (!cancelled) setLoading(false)
      clearTimeout(timeout)
    })()
    return () => {
      cancelled = true
      clearTimeout(timeout)
    }
  }, [user, studyId, fetchStatus, fetchContacts, fetchDistStatus, fetchDistributions, fetchDistConfig])

  useEffect(() => {
    if (studyId && distStatus.busy) {
      const t = setInterval(fetchDistStatus, POLL_INTERVAL_MS)
      return () => clearInterval(t)
    }
  }, [studyId, distStatus.busy, fetchDistStatus])

  const handleCheck = async () => {
    if (!studyId) return
    setChecking(true)
    setError(null)
    setCheckResult(null)
    try {
      const res = await getStudyDistributionCheck(studyId)
      setCheckResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setChecking(false)
    }
  }

  const handlePreview = async () => {
    if (!studyId) return
    setLoadingPreview(true)
    setError(null)
    setPreviewResult(null)
    try {
      const res = await getStudyDistributionSendPreview(studyId)
      setPreviewResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingPreview(false)
    }
  }

  const handleSend = async () => {
    if (!studyId || !canEdit) return
    setSending(true)
    setError(null)
    setMessage(null)
    try {
      const options = {}
      const limitNum = sendLimit.trim() === '' ? null : parseInt(sendLimit, 10)
      if (limitNum != null && !Number.isNaN(limitNum) && limitNum > 0) options.limit = limitNum
      const indicesStr = sendIndices.trim()
      if (indicesStr) {
        const arr = indicesStr.split(',').map((s) => parseInt(s.trim(), 10)).filter((n) => !Number.isNaN(n))
        if (arr.length) options.contactIndices = arr
      }
      if (bypassTimeSlot) options.bypassTimeSlot = true
      await postStudyDistributionSend(studyId, Object.keys(options).length ? options : undefined)
      setMessage('Send started. Status will update automatically.')
      await fetchDistStatus()
      await fetchDistributions()
    } catch (e) {
      setError(e.message)
    } finally {
      setSending(false)
    }
  }

  const handleDeleteUnsent = async () => {
    if (!studyId || !canEdit) return
    setDeleting(true)
    setError(null)
    setMessage(null)
    try {
      let options = null
      if (deleteAllUnsent) {
        options = { allUnsent: true }
      } else if (deleteContactId.trim() !== '') {
        options = { contactId: deleteContactId.trim() }
      } else if (deleteIndex.trim() !== '') {
        const index = parseInt(deleteIndex, 10)
        if (Number.isNaN(index) || index < 0) {
          setError('Index must be a non-negative number, or use contact ID / "Delete all unsent".')
          setDeleting(false)
          return
        }
        options = { index }
      }
      const res = await postStudyDistributionDeleteUnsent(studyId, options)
      setMessage(`Deleted ${res.deleted} unsent distribution(s).`)
      if (res.errors?.length) setError(res.errors.join('; '))
      await fetchContacts()
      await fetchDistributions()
    } catch (e) {
      setError(e.message)
    } finally {
      setDeleting(false)
    }
  }

  const handleExport = async (format = 'json') => {
    if (!studyId) return
    setExportLoading(true)
    setError(null)
    setExportResult(null)
    try {
      const res = await postStudyDistributionExport(studyId, { format })
      setExportResult(res)
      setMessage(`Export complete. File path: ${res.path}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setExportLoading(false)
    }
  }

  const handleStartEditContact = (contact) => {
    setEditingContactId(contact.id)
    setEditDraft({
      SurveysSchedule: contact.embeddedData?.SurveysSchedule ?? '',
      UseSMS: contact.embeddedData?.UseSMS ?? '',
      UseEmail: contact.embeddedData?.UseEmail ?? '',
      DeleteUnsent: contact.embeddedData?.DeleteUnsent ?? '',
    })
  }

  const handleSaveContactEdit = async () => {
    if (!studyId || !canEdit || !editingContactId || !editDraft) return
    setError(null)
    try {
      await patchStudyDistributionContact(studyId, editingContactId, editDraft)
      setEditingContactId(null)
      setEditDraft(null)
      setMessage('Contact updated.')
      await fetchContacts()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleCancelEditContact = () => {
    setEditingContactId(null)
    setEditDraft(null)
  }

  const handleDistConfigChange = (key, value) => {
    setDistConfigForm((f) => ({ ...f, [key]: value }))
  }

  const handleSaveDistConfig = async () => {
    if (!studyId || !canEdit) return
    setDistConfigSaving(true)
    setError(null)
    setMessage(null)
    try {
      const res = await getStudyConfig(studyId)
      const fullConfig = res?.config || {}
      const merged = { ...fullConfig, ...distConfigForm }
      await saveStudyConfig(studyId, merged)
      setMessage('Distribution settings saved.')
    } catch (e) {
      setError(e?.message || 'Failed to save.')
    } finally {
      setDistConfigSaving(false)
    }
  }

  const clearFeedback = () => {
    setError(null)
    setMessage(null)
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Checking auth…</p>
      </div>
    )
  }

  if (!studyId) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">No study selected.</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Loading…</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header
        status={status || 'idle'}
        onStart={() => {}}
        onStop={() => {}}
        starting={false}
        stopping={false}
        configOverrides={{}}
        canEdit={canEdit}
        showRunControls={false}
      />
      <main className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
        <Breadcrumb
          items={[
            { label: 'Dashboard', to: '/studies' },
            { label: studyName, to: `/studies/${studyId}` },
            { label: 'Distribution' },
          ]}
        />
        <PageHeader
          title="Distribution & Mailing List"
          description="Send survey invitations (SMS or email) from your Qualtrics mailing list. Configure directory, mailing list, and message IDs in the settings card below."
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link to={`/studies/${studyId}`} className="gap-1.5">
                <ArrowLeft className="size-4" aria-hidden />
                Back to Study
              </Link>
            </Button>
          }
        />

        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <Sliders className="size-4" />
                Distribution Settings
              </CardTitle>
              <CardDescription>
                Qualtrics directory, mailing list, message library, and send options. Save after editing.
              </CardDescription>
            </div>
            {canEdit && (
              <Button onClick={handleSaveDistConfig} disabled={distConfigSaving} className="shrink-0">
                {distConfigSaving ? 'Saving…' : 'Save Settings'}
              </Button>
            )}
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              {DISTRIBUTION_CONFIG_KEYS.map((key) => (
                <div key={key} className="space-y-2">
                  <Label htmlFor={`dist-${key}`} className="text-muted-foreground text-xs">
                    {DISTRIBUTION_CONFIG_LABELS[key] || key}
                  </Label>
                  {key === 'QUALTRICS_CONTACT_METHOD' ? (
                    <select
                      id={`dist-${key}`}
                      value={(distConfigForm[key] ?? '').trim() || 'email'}
                      onChange={(e) => handleDistConfigChange(key, e.target.value)}
                      disabled={!canEdit}
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm disabled:opacity-50"
                    >
                      {DISTRIBUTION_CONTACT_METHODS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      id={`dist-${key}`}
                      type="text"
                      value={distConfigForm[key] === '********' ? '********' : (distConfigForm[key] ?? '')}
                      onChange={(e) => handleDistConfigChange(key, e.target.value)}
                      placeholder={key.includes('TIME_SLOTS') ? '[[800,900],[1200,1300]]' : ''}
                      readOnly={!canEdit}
                      disabled={!canEdit}
                      className="font-mono text-sm"
                    />
                  )}
                </div>
              ))}
            </div>
            {!canEdit && (
              <p className="text-xs text-muted-foreground">You need editor or admin access to change these settings.</p>
            )}
            <p className="text-xs text-muted-foreground border-t border-border pt-3">
              Qualtrics survey ID, API token, and other pipeline settings are in{' '}
              <Link to={`/studies/${studyId}`} className="text-primary underline hover:no-underline">Study Dashboard</Link> → Connections &amp; Settings.
            </p>
          </CardContent>
        </Card>

        {(error || message) && (
          <div className="space-y-2">
            {error && (
              <Alert variant="destructive" className="flex items-start justify-between gap-2">
                <div>
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </div>
                <Button variant="ghost" size="sm" className="shrink-0" onClick={clearFeedback} aria-label="Dismiss">
                  <XCircle className="size-4" />
                </Button>
              </Alert>
            )}
            {message && (
              <Alert className="flex items-start justify-between gap-2">
                <div>
                  <AlertTitle>Info</AlertTitle>
                  <AlertDescription>{message}</AlertDescription>
                </div>
                <Button variant="ghost" size="sm" className="shrink-0" onClick={clearFeedback} aria-label="Dismiss">
                  <XCircle className="size-4" />
                </Button>
              </Alert>
            )}
          </div>
        )}

        <section className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Validate Setup</CardTitle>
              <CardDescription>
                Verify survey, mailing list, and message IDs are valid in Qualtrics before sending.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button variant="outline" onClick={handleCheck} disabled={checking} className="w-full sm:w-auto">
                {checking ? 'Checking…' : 'Check IDs'}
              </Button>
              {checkResult && (
                <div className="space-y-2 rounded-lg border border-border bg-muted/30 p-3 text-sm">
                  {checkResult.ok ? (
                    <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="size-4 shrink-0" />
                      <span className="font-medium">All IDs valid</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-destructive">
                      <XCircle className="size-4 shrink-0" />
                      <span className="font-medium">Validation failed</span>
                    </div>
                  )}
                  {checkResult.details && Object.keys(checkResult.details).length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(checkResult.details).map(([key, val]) => (
                        <Badge key={key} variant="secondary" className="font-normal">
                          {key.replace(/_/g, ' ')}: {val}
                        </Badge>
                      ))}
                    </div>
                  )}
                  {checkResult.errors?.length > 0 && (
                    <ul className="list-disc list-inside space-y-0.5 text-destructive">
                      {checkResult.errors.map((err, i) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ListFilter className="size-4" />
                Send Preview
              </CardTitle>
              <CardDescription>
                See how many contacts would receive a send right now (no messages are sent).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button variant="outline" onClick={handlePreview} disabled={loadingPreview} className="w-full sm:w-auto">
                {loadingPreview ? 'Loading…' : 'Preview send'}
              </Button>
              {previewResult && (
                <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm space-y-2">
                  <p>
                    <strong>{previewResult.count ?? 0}</strong> contact(s) would be sent to
                    {previewResult.inTimeSlot === false && (
                      <span className="ml-1 text-amber-600 dark:text-amber-400">(outside configured time slot)</span>
                    )}
                  </p>
                  {previewResult.contacts?.length > 0 && (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-muted-foreground">Show list</summary>
                      <ul className="mt-1 list-inside list-disc text-muted-foreground">
                        {previewResult.contacts.slice(0, 20).map((c, i) => (
                          <li key={i}>{c.name || c.email || c.phone || c.id}</li>
                        ))}
                        {previewResult.contacts.length > 20 && (
                          <li className="text-muted-foreground">… and {previewResult.contacts.length - 20} more</li>
                        )}
                      </ul>
                    </details>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Send className="size-4" />
                Send Invitations
              </CardTitle>
              <CardDescription>
                Send distributions for contacts that are scheduled and not yet sent (SMS or email per contact method).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {canEdit ? (
                <>
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="space-y-1">
                      <Label htmlFor="send-limit" className="text-muted-foreground text-xs">Limit (optional)</Label>
                      <Input
                        id="send-limit"
                        type="number"
                        min={1}
                        placeholder="All"
                        value={sendLimit}
                        onChange={(e) => setSendLimit(e.target.value)}
                        className="w-24"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="send-indices" className="text-muted-foreground text-xs">Indices (optional)</Label>
                      <Input
                        id="send-indices"
                        type="text"
                        placeholder="0,1,2"
                        value={sendIndices}
                        onChange={(e) => setSendIndices(e.target.value)}
                        className="w-32"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        id="bypass-time-slot"
                        type="checkbox"
                        checked={bypassTimeSlot}
                        onChange={(e) => setBypassTimeSlot(e.target.checked)}
                        className="rounded border-border"
                      />
                      <Label htmlFor="bypass-time-slot" className="text-xs text-muted-foreground">Bypass time slot</Label>
                    </div>
                  </div>
                  <Button
                    onClick={handleSend}
                    disabled={sending || distStatus.busy}
                    className="w-full sm:w-auto"
                  >
                    {sending ? 'Starting…' : distStatus.busy ? 'Sending…' : 'Send distributions'}
                  </Button>
                  {(distStatus.busy || distStatus.lastResult) && (
                    <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
                      {distStatus.busy ? (
                        <p className="text-muted-foreground">Send in progress…</p>
                      ) : distStatus.lastResult ? (
                        <p>
                          Last send: <strong>{distStatus.lastResult.sent ?? 0}</strong> sent
                          {distStatus.lastResult.errors?.length > 0 && (
                            <span className="mt-1 block text-destructive">
                              Errors: {distStatus.lastResult.errors.join('; ')}
                            </span>
                          )}
                        </p>
                      ) : null}
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">You need editor or admin access to send.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle className="text-base">Distributions</CardTitle>
                <CardDescription>
                  Email and SMS distributions for this survey. Refresh after send/delete.
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={fetchDistributions} disabled={loadingDistributions} className="shrink-0">
                {loadingDistributions ? 'Loading…' : 'Refresh'}
              </Button>
            </CardHeader>
            <CardContent>
              {loadingDistributions ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
              ) : (
                <div className="space-y-2 text-sm">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary">
                      Email: {distributionsList.email?.length ?? 0} total
                    </Badge>
                    <Badge variant="outline">
                      Not sent: {distributionsList.email?.filter((d) => d.status === 'Not Sent').length ?? 0}
                    </Badge>
                    <Badge variant="outline">
                      Sent: {distributionsList.email?.filter((d) => d.status === 'Sent').length ?? 0}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary">
                      SMS: {distributionsList.sms?.length ?? 0} total
                    </Badge>
                    <Badge variant="outline">
                      Not sent: {distributionsList.sms?.filter((d) => d.status === 'Not Sent').length ?? 0}
                    </Badge>
                    <Badge variant="outline">
                      Sent: {distributionsList.sms?.filter((d) => d.status === 'Sent').length ?? 0}
                    </Badge>
                  </div>
                  {distributionsList.errors?.length > 0 && (
                    <p className="text-destructive text-xs">{distributionsList.errors.join('; ')}</p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        {canEdit && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Delete Unsent</CardTitle>
              <CardDescription>
                Remove unsent distributions. Choose one: contact index, contact ID, or delete all unsent for this survey.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-end gap-3">
                <div className="space-y-1">
                  <Label htmlFor="delete-index" className="text-muted-foreground text-xs">Index</Label>
                  <Input
                    id="delete-index"
                    type="text"
                    placeholder="e.g. 0"
                    value={deleteIndex}
                    onChange={(e) => { setDeleteIndex(e.target.value); setDeleteContactId(''); setDeleteAllUnsent(false); }}
                    className="w-24"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="delete-contact-id" className="text-muted-foreground text-xs">Contact ID</Label>
                  <Input
                    id="delete-contact-id"
                    type="text"
                    placeholder="Qualtrics contact ID"
                    value={deleteContactId}
                    onChange={(e) => { setDeleteContactId(e.target.value); setDeleteIndex(''); setDeleteAllUnsent(false); }}
                    className="w-48"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <input
                    id="delete-all-unsent"
                    type="checkbox"
                    checked={deleteAllUnsent}
                    onChange={(e) => { setDeleteAllUnsent(e.target.checked); setDeleteIndex(''); setDeleteContactId(''); }}
                    className="rounded border-border"
                  />
                  <Label htmlFor="delete-all-unsent" className="text-xs text-muted-foreground">Delete all unsent</Label>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Otherwise (no index/ID/all): deletes only for contacts with embedded DeleteUnsent=1.
              </p>
              <Button variant="destructive" onClick={handleDeleteUnsent} disabled={deleting}>
                {deleting ? 'Deleting…' : 'Delete unsent'}
              </Button>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FileDown className="size-4" />
              Export Responses
            </CardTitle>
            <CardDescription>
              Export survey responses from Qualtrics (JSON or CSV). File is saved on the server; path is shown below.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-3">
            <Button variant="outline" size="sm" onClick={() => handleExport('json')} disabled={exportLoading}>
              {exportLoading ? 'Exporting…' : 'Export JSON'}
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleExport('csv')} disabled={exportLoading}>
              {exportLoading ? 'Exporting…' : 'Export CSV'}
            </Button>
            {exportResult?.path && (
              <p className="text-sm text-muted-foreground">
                Saved: <code className="rounded bg-muted px-1">{exportResult.path}</code>
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base">Contacts</CardTitle>
              <CardDescription>
                Mailing list contacts from Qualtrics. Use &quot;Refresh&quot; to reload after changes in Qualtrics or after delete.
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={fetchContacts} disabled={loadingContacts} className="shrink-0">
              {loadingContacts ? 'Loading…' : 'Refresh'}
            </Button>
          </CardHeader>
          <CardContent>
            {contacts.length === 0 && !loadingContacts ? (
              <div className="rounded-lg border border-dashed border-border bg-muted/20 py-12 text-center">
                <p className="text-sm text-muted-foreground">
                  No contacts loaded. Set directory and mailing list in the Distribution Settings above, then click Refresh.
                </p>
              </div>
            ) : (
              <Table className="min-w-[720px]">
                <TableHeader>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableHead scope="col">#</TableHead>
                    <TableHead scope="col">Name</TableHead>
                    <TableHead scope="col">Email</TableHead>
                    <TableHead scope="col">Phone</TableHead>
                    <TableHead scope="col" className="text-muted-foreground">Scheduled</TableHead>
                    <TableHead scope="col" className="text-muted-foreground">Use SMS</TableHead>
                    <TableHead scope="col" className="text-muted-foreground">Use email</TableHead>
                    <TableHead scope="col" className="text-muted-foreground">Delete unsent</TableHead>
                    {canEdit ? <TableHead scope="col" className="w-28 text-muted-foreground">Actions</TableHead> : null}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {contacts.map((c) => {
                    const isEditing = editingContactId === c.id
                    return (
                      <TableRow key={c.id || c.index}>
                        <TableCell className="font-mono text-muted-foreground">{c.index}</TableCell>
                        <TableCell>{c.name || `${c.firstName || ''} ${c.lastName || ''}`.trim() || '—'}</TableCell>
                        <TableCell>{c.email || '—'}</TableCell>
                        <TableCell>{c.phone || '—'}</TableCell>
                        {isEditing && editDraft ? (
                          <>
                            <TableCell className="p-2">
                              <Input
                                value={editDraft.SurveysSchedule}
                                onChange={(e) => setEditDraft((d) => ({ ...d, SurveysSchedule: e.target.value }))}
                                className="h-8 w-16 text-xs"
                                placeholder="0"
                              />
                            </TableCell>
                            <TableCell className="p-2">
                              <Input
                                value={editDraft.UseSMS}
                                onChange={(e) => setEditDraft((d) => ({ ...d, UseSMS: e.target.value }))}
                                className="h-8 w-12 text-xs"
                                placeholder="1"
                              />
                            </TableCell>
                            <TableCell className="p-2">
                              <Input
                                value={editDraft.UseEmail}
                                onChange={(e) => setEditDraft((d) => ({ ...d, UseEmail: e.target.value }))}
                                className="h-8 w-12 text-xs"
                                placeholder="1"
                              />
                            </TableCell>
                            <TableCell className="p-2">
                              <Input
                                value={editDraft.DeleteUnsent}
                                onChange={(e) => setEditDraft((d) => ({ ...d, DeleteUnsent: e.target.value }))}
                                className="h-8 w-12 text-xs"
                                placeholder="0"
                              />
                            </TableCell>
                            {canEdit ? (
                              <TableCell className="p-2">
                                <div className="flex items-center gap-1">
                                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleSaveContactEdit} aria-label="Save">
                                    <Check className="size-4 text-emerald-600" />
                                  </Button>
                                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleCancelEditContact} aria-label="Cancel">
                                    <X className="size-4" />
                                  </Button>
                                </div>
                              </TableCell>
                            ) : null}
                          </>
                        ) : (
                          <>
                            <TableCell className="text-muted-foreground">{c.scheduled ?? '—'}</TableCell>
                            <TableCell className="text-muted-foreground">{c.useSMS ?? '—'}</TableCell>
                            <TableCell className="text-muted-foreground">{c.useEmail ?? '—'}</TableCell>
                            <TableCell className="text-muted-foreground">{c.deleteUnsent ?? '—'}</TableCell>
                            {canEdit ? (
                              <TableCell className="p-2">
                                <Button variant="ghost" size="sm" className="h-8 gap-1" onClick={() => handleStartEditContact(c)} aria-label="Edit contact">
                                  <Pencil className="size-3.5" />
                                  Edit
                                </Button>
                              </TableCell>
                            ) : null}
                          </>
                        )}
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
