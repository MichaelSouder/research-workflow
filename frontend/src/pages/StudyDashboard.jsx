import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  getStudyStatus,
  getStudyActivity,
  getStudyErrors,
  startStudyRun,
  stopStudyRun,
  getStudyConfig,
  saveStudyConfig,
  getStudies,
} from '../api'
import { canEditStudy } from '../lib/roles'
import { useAuth } from '../contexts/AuthContext'
import { POLL_INTERVAL_MS, STATUS_LABELS } from '../constants'
import Header from '../components/Header'
import Breadcrumb from '../components/Breadcrumb'
import PageHeader from '../components/PageHeader'
import PageSection from '../components/PageSection'
import PipelineStrip from '../components/PipelineStrip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import ProgressBar from '../components/ProgressBar'
import ActivityStream from '../components/ActivityStream'
import ErrorLog from '../components/ErrorLog'
import Settings from '../components/Settings'

export default function StudyDashboard() {
  const { studyId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [studies, setStudies] = useState([])
  const [currentStudyRoleCanonical, setCurrentStudyRoleCanonical] = useState(null)
  const [status, setStatus] = useState(null)
  const [activity, setActivity] = useState([])
  const [errors, setErrors] = useState([])
  const [currentStep, setCurrentStep] = useState('')
  const [progressPercent, setProgressPercent] = useState(0)
  const [message, setMessage] = useState('')
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [settingsForm, setSettingsForm] = useState({})

  useEffect(() => {
    if (!user) return
    let cancelled = false
    getStudies()
      .then((data) => {
        if (cancelled) return
        setStudies(data.studies || [])
      })
      .catch(() => {
        if (!cancelled) setStudies([])
      })
    return () => { cancelled = true }
  }, [user])

  const fetchStatus = useCallback(async () => {
    if (!studyId) return null
    try {
      const s = await getStudyStatus(studyId)
      setStatus(s.status)
      setCurrentStep(s.currentStep)
      setProgressPercent(s.progressPercent ?? 0)
      setMessage(s.message ?? '')
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
      setError(e.message)
      return null
    }
  }, [navigate, studyId])

  const fetchActivity = useCallback(async () => {
    if (!studyId) return
    try {
      const { activity: a } = await getStudyActivity(studyId)
      setActivity(a || [])
    } catch (_) {}
  }, [studyId])

  const fetchErrors = useCallback(async () => {
    if (!studyId) return
    try {
      const { errors: e } = await getStudyErrors(studyId)
      setErrors(e || [])
    } catch (_) {}
  }, [studyId])

  const fetchConfig = useCallback(async () => {
    if (!studyId) return
    try {
      const c = await getStudyConfig(studyId)
      setConfig(c)
      const roleStudy = studies.find((s) => s.id === studyId)
      if (roleStudy) setCurrentStudyRoleCanonical(roleStudy.roleCanonical)
    } catch (_) {}
  }, [studyId, studies])

  useEffect(() => {
    if (!user || !studyId) return
    let cancelled = false
    const stopLoading = () => {
      if (!cancelled) setLoading(false)
    }
    const timeout = setTimeout(() => {
      stopLoading()
      if (!cancelled) setError('Backend took too long. Is it running? (default port 48721)')
    }, 5000)
    ;(async () => {
      try {
        await fetchStatus()
        await fetchActivity()
        await fetchErrors()
        await fetchConfig()
      } catch (_) {
        if (!cancelled) setError('Could not reach backend.')
      } finally {
        clearTimeout(timeout)
        stopLoading()
      }
    })()
    return () => {
      cancelled = true
      clearTimeout(timeout)
    }
  }, [user, studyId, fetchStatus, fetchActivity, fetchErrors, fetchConfig])

  useEffect(() => {
    if (studyId && status === 'running') {
      const t = setInterval(async () => {
        await fetchStatus()
        await fetchActivity()
        await fetchErrors()
      }, POLL_INTERVAL_MS)
      return () => clearInterval(t)
    }
  }, [studyId, status, fetchStatus, fetchActivity, fetchErrors])

  const canEdit = canEditStudy(currentStudyRoleCanonical)
  const currentStudyName = studies.find((s) => s.id === studyId)?.name ?? studyId

  const handleStart = async (configOverrides = null) => {
    if (!studyId || !canEdit) return
    setError(null)
    setStarting(true)
    try {
      const overrides = configOverrides
        ? Object.fromEntries(
            Object.entries(configOverrides).filter(
              ([, v]) => v != null && v !== '' && v !== '********'
            )
          )
        : null
      await startStudyRun(studyId, overrides && Object.keys(overrides).length ? overrides : null)
      await fetchStatus()
      await fetchActivity()
      await fetchErrors()
    } catch (e) {
      setError(e.message)
    } finally {
      setStarting(false)
    }
  }

  const handleStop = async () => {
    if (!studyId || !canEdit) return
    setStopping(true)
    try {
      await stopStudyRun(studyId)
      await fetchStatus()
      await fetchActivity()
    } catch (e) {
      setError(e.message)
    } finally {
      setStopping(false)
    }
  }

  const handleSaveConfig = async (newConfig, persist) => {
    if (!studyId || !canEdit) return
    setSaving(true)
    try {
      await saveStudyConfig(studyId, newConfig, persist)
      await fetchConfig()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
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
      <div className="min-h-screen bg-background text-foreground">
        <main className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-full max-w-md" />
          <Skeleton className="h-40 w-full rounded-xl border border-border" />
          <div className="grid gap-4 md:grid-cols-2">
            <Skeleton className="h-64 w-full rounded-xl border border-border" />
            <Skeleton className="h-64 w-full rounded-xl border border-border" />
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header
        status={status || 'idle'}
        onStart={handleStart}
        onStop={handleStop}
        starting={starting}
        stopping={stopping}
        configOverrides={settingsForm}
        canEdit={canEdit}
      />
      <main className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
        <Breadcrumb
          items={[
            { label: 'Dashboard', to: '/studies' },
            { label: currentStudyName },
          ]}
          className="mb-2"
        />
        <PageHeader
          title={currentStudyName}
          description="Run the pipeline, manage connections, and review activity and errors for this study."
        />
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <Card className="border-border shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Run Status</CardTitle>
            <CardDescription>Current pipeline run at a glance.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="text-xs font-medium text-muted-foreground">Status</dt>
                <dd className="mt-1">
                  <Badge variant={status === 'failed' ? 'destructive' : status === 'running' ? 'default' : 'secondary'}>
                    {STATUS_LABELS[status] ?? status ?? '—'}
                  </Badge>
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-muted-foreground">Current Step</dt>
                <dd className="mt-1 text-sm text-foreground">{currentStep || '—'}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-muted-foreground">Progress</dt>
                <dd className="mt-1 text-sm font-medium tabular-nums text-foreground">
                  {typeof progressPercent === 'number' ? `${progressPercent}%` : '—'}
                </dd>
              </div>
              <div className="sm:col-span-2 lg:col-span-1">
                <dt className="text-xs font-medium text-muted-foreground">Message</dt>
                <dd className="mt-1 line-clamp-3 text-sm text-muted-foreground">{message || '—'}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>
        <section aria-labelledby="pipeline-heading" className="space-y-3">
          <h2 id="pipeline-heading" className="text-sm font-medium text-foreground">
            Pipeline Stages
          </h2>
          <PipelineStrip status={status} currentStep={currentStep} />
          <div>
            <ProgressBar
              status={status}
              currentStep={currentStep}
              progressPercent={progressPercent}
              message={message}
            />
          </div>
        </section>
        <PageSection title="Connections & Settings" description="Qualtrics, Grid, Box, and other integration settings for this study." asCard={false}>
          <Settings
            studyId={studyId}
            config={config}
            onSave={handleSaveConfig}
            saving={saving}
            onFormChange={setSettingsForm}
            readOnly={!canEdit}
            onRevealSecret={async (key) => {
              const res = await getStudyConfig(studyId, true)
              return res.config?.[key] ?? ''
            }}
          />
        </PageSection>
        <PageSection title="Activity & Errors" description="Live log lines from the latest run for this study." asCard={false}>
          <div className="grid gap-4 md:grid-cols-2">
            <ActivityStream activity={activity} />
            <ErrorLog errors={errors} />
          </div>
        </PageSection>
      </main>
    </div>
  )
}
