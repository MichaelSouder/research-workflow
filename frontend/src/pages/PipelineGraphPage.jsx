import { useState, useEffect, useCallback, useRef } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  getStudyStatus,
  getStudies,
  getStudyConfig,
  saveStudyConfig,
  startStudyRun,
  stopStudyRun,
  getStudyPipelines,
  getStudyPipeline,
  saveStudyPipeline,
  createStudyPipeline,
  subscribePipelineStream,
} from '../api'
import { canEditStudy } from '../lib/roles'
import { useAuth } from '../contexts/AuthContext'
import { POLL_INTERVAL_MS, STATUS_LABELS } from '../constants'
import Header from '../components/Header'
import Breadcrumb from '../components/Breadcrumb'
import PageHeader from '../components/PageHeader'
import PipelineFlow from '../components/PipelineFlow/PipelineFlow'
import PipelineNodeConfigPanel from '../components/PipelineFlow/PipelineNodeConfigPanel'
import PipelineNodePalette from '../components/PipelineFlow/PipelineNodePalette'
import { NODE_CONFIG } from '../components/PipelineFlow/componentConfig'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ArrowLeft, Plus, Circle, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

const DEFAULT_PIPELINE_ID = '__default__'

const DEFAULT_PIPELINE_DEFINITION = {
  nodes: [
    { id: 'qualtrics', type: 'qualtrics', position: { x: 0, y: 0 }, data: { label: 'Qualtrics' } },
    { id: 'process', type: 'process', position: { x: 220, y: 0 }, data: { label: 'Process' } },
    { id: 'grid', type: 'grid', position: { x: 440, y: 0 }, data: { label: 'Grid' } },
    { id: 'box', type: 'box', position: { x: 660, y: 0 }, data: { label: 'Box' } },
  ],
  edges: [
    { id: 'e-qualtrics-process', source: 'qualtrics', target: 'process' },
    { id: 'e-process-grid', source: 'process', target: 'grid' },
    { id: 'e-grid-box', source: 'grid', target: 'box' },
  ],
}

/** Preset pipeline templates for "New from template". */
const PIPELINE_TEMPLATES = [
  {
    id: 'full',
    name: 'Qualtrics → Process → Grid → Box',
    description: 'Full flow: export, normalize, fraud check, Grid subjects, Box upload.',
    ...DEFAULT_PIPELINE_DEFINITION,
  },
  {
    id: 'qualtrics-process-box',
    name: 'Qualtrics → Process → Box',
    description: 'Export, process, and upload to Box only (no Grid).',
    nodes: [
      { id: 'qualtrics', type: 'qualtrics', position: { x: 0, y: 0 }, data: { label: 'Qualtrics' } },
      { id: 'process', type: 'process', position: { x: 220, y: 0 }, data: { label: 'Process' } },
      { id: 'box', type: 'box', position: { x: 440, y: 0 }, data: { label: 'Box' } },
    ],
    edges: [
      { id: 'e-qualtrics-process', source: 'qualtrics', target: 'process' },
      { id: 'e-process-box', source: 'process', target: 'box' },
    ],
  },
  {
    id: 'qualtrics-webhook',
    name: 'Qualtrics → Webhook',
    description: 'Export and send data to an external URL.',
    nodes: [
      { id: 'qualtrics', type: 'qualtrics', position: { x: 0, y: 0 }, data: { label: 'Qualtrics' } },
      { id: 'webhook', type: 'webhook', position: { x: 220, y: 0 }, data: { label: 'Webhook' } },
    ],
    edges: [
      { id: 'e-qualtrics-webhook', source: 'qualtrics', target: 'webhook' },
    ],
  },
  {
    id: 'process-only',
    name: 'Process only (normalize + fraud)',
    description: 'Single process node for testing or reuse in another pipeline.',
    nodes: [
      { id: 'process', type: 'process', position: { x: 0, y: 0 }, data: { label: 'Process' } },
    ],
    edges: [],
  },
]

export default function PipelineGraphPage() {
  const { studyId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [studies, setStudies] = useState([])
  const [currentStudyRoleCanonical, setCurrentStudyRoleCanonical] = useState(null)
  const [status, setStatus] = useState(null)
  const [currentStep, setCurrentStep] = useState('')
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [error, setError] = useState(null)
  const [selectedNodeId, setSelectedNodeId] = useState(null)
  const [config, setConfig] = useState(null)
  const [pipelines, setPipelines] = useState([])
  const [currentPipelineId, setCurrentPipelineId] = useState(null)
  const [currentPipelineName, setCurrentPipelineName] = useState('')
  const [definition, setDefinition] = useState({ nodes: [], edges: [] })
  const [savingPipeline, setSavingPipeline] = useState(false)
  const [saveAsName, setSaveAsName] = useState('')
  const [showSaveAs, setShowSaveAs] = useState(false)
  const [showNewPipeline, setShowNewPipeline] = useState(false)
  const [showTemplateModal, setShowTemplateModal] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [selectedTemplateId, setSelectedTemplateId] = useState(null)
  const [newPipelineName, setNewPipelineName] = useState('')
  const [creatingPipeline, setCreatingPipeline] = useState(false)
  const [streamStatus, setStreamStatus] = useState('idle')
  const currentPipelineIdRef = useRef(currentPipelineId)
  currentPipelineIdRef.current = currentPipelineId

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
      setCurrentStep(s.currentStep ?? '')
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

  const fetchConfig = useCallback(async () => {
    if (!studyId) return
    try {
      const res = await getStudyConfig(studyId)
      setConfig(res)
      const roleStudy = studies.find((s) => s.id === studyId)
      if (roleStudy) setCurrentStudyRoleCanonical(roleStudy.roleCanonical)
    } catch (_) {}
  }, [studyId, studies])

  const fetchPipelines = useCallback(async () => {
    if (!studyId) return
    try {
      const res = await getStudyPipelines(studyId)
      const list = Array.isArray(res.pipelines) ? res.pipelines : []
      setPipelines(list.length > 0 ? list : [{ id: DEFAULT_PIPELINE_ID, name: 'Default', isDefault: true }])
      const defaultPipeline = list.find((p) => p.isDefault) || list[0] || { id: DEFAULT_PIPELINE_ID, name: 'Default', isDefault: true }
      const pipelineId = defaultPipeline?.id ?? DEFAULT_PIPELINE_ID
      if (!currentPipelineId || !list.find((p) => p.id === currentPipelineId)) {
        setCurrentPipelineId(pipelineId)
        setCurrentPipelineName(defaultPipeline?.name ?? 'Default')
      }
    } catch (_) {
      setPipelines([{ id: DEFAULT_PIPELINE_ID, name: 'Default', isDefault: true }])
      setCurrentPipelineId((prev) => prev || DEFAULT_PIPELINE_ID)
      setCurrentPipelineName((prev) => prev || 'Default')
    }
  }, [studyId])

  const fetchPipelineDefinition = useCallback(async () => {
    if (!studyId || !currentPipelineId) return
    const pipelineIdForFetch = currentPipelineId
    try {
      const res = await getStudyPipeline(studyId, pipelineIdForFetch)
      const nodes = Array.isArray(res.nodes) ? res.nodes : []
      const edges = Array.isArray(res.edges) ? res.edges : []
      if (currentPipelineIdRef.current !== pipelineIdForFetch) return
      setDefinition({ nodes, edges })
      if (res.name != null) setCurrentPipelineName(res.name)
    } catch (_) {
      if (currentPipelineIdRef.current !== pipelineIdForFetch) return
      if (pipelineIdForFetch === DEFAULT_PIPELINE_ID) {
        setDefinition({ ...DEFAULT_PIPELINE_DEFINITION })
      } else {
        setDefinition({ nodes: [], edges: [] })
      }
    }
  }, [studyId, currentPipelineId])

  const handleAddNode = useCallback((nodeType) => {
    const existingIds = definition.nodes.map((n) => n.id)
    let id = nodeType
    let i = 1
    while (existingIds.includes(id)) {
      id = `${nodeType}_${i}`
      i += 1
    }
    const maxX = definition.nodes.length
      ? Math.max(...definition.nodes.map((n) => (n.position?.x ?? 0)))
      : -220
    const label = NODE_CONFIG[nodeType]?.label ?? nodeType.charAt(0).toUpperCase() + nodeType.slice(1)
    const newNode = {
      id,
      type: nodeType,
      position: { x: maxX + 220, y: 0 },
      data: { label },
    }
    setDefinition({
      nodes: [...definition.nodes, newNode],
      edges: definition.edges,
    })
  }, [definition])

  const handleRemoveSelectedNode = useCallback(() => {
    if (!selectedNodeId || definition.nodes.length <= 1) return
    const nextNodes = definition.nodes.filter((n) => n.id !== selectedNodeId)
    const nextEdges = definition.edges.filter(
      (e) => e.source !== selectedNodeId && e.target !== selectedNodeId
    )
    setDefinition({ nodes: nextNodes, edges: nextEdges })
    setSelectedNodeId(null)
  }, [selectedNodeId, definition])

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
        await fetchConfig()
        await fetchPipelines()
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
  }, [user, studyId, studies, fetchStatus, fetchConfig, fetchPipelines])

  useEffect(() => {
    if (!studyId || currentPipelineId == null) return
    setDefinition({ nodes: [], edges: [] })
    fetchPipelineDefinition()
  }, [studyId, currentPipelineId, fetchPipelineDefinition])

  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedNodeId && definition.nodes?.length > 1) {
        e.preventDefault()
        handleRemoveSelectedNode()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [selectedNodeId, definition?.nodes?.length, handleRemoveSelectedNode])

  useEffect(() => {
    if (studyId && status === 'running') {
      const t = setInterval(fetchStatus, POLL_INTERVAL_MS)
      return () => clearInterval(t)
    }
  }, [studyId, status, fetchStatus])

  // SSE subscription for hot reload when another tab or service updates the pipeline
  useEffect(() => {
    if (!studyId || !currentPipelineId || loading) return
    const sub = subscribePipelineStream(studyId, currentPipelineId, {
      onStatus: (s) => setStreamStatus(s),
      onEvent: (payload) => {
        if (payload.event === 'updated' || payload.event === 'created') {
          if (payload.pipelineId === currentPipelineId) {
            setDefinition({ nodes: payload.nodes || [], edges: payload.edges || [] })
            if (payload.name != null) setCurrentPipelineName(payload.name)
            toast.info('Pipeline updated from another tab or service.')
          }
        } else if (payload.event === 'deleted' && payload.pipelineId === currentPipelineId) {
          toast.warning('Pipeline was deleted.')
          getStudyPipelines(studyId).then((res) => {
            const list = res.pipelines || []
            const defaultP = list.find((p) => p.isDefault) || list[0]
            const nextId = defaultP?.id ?? DEFAULT_PIPELINE_ID
            setPipelines(list.length ? list : [{ id: DEFAULT_PIPELINE_ID, name: 'Default', isDefault: true }])
            setCurrentPipelineId(nextId)
            setCurrentPipelineName(defaultP?.name ?? 'Default')
          })
        }
      },
    })
    return () => sub.unsubscribe()
  }, [studyId, currentPipelineId, loading])

  const canEdit = canEditStudy(currentStudyRoleCanonical)
  const currentStudyName = studies.find((s) => s.id === studyId)?.name ?? studyId
  const selectedPipelineMeta = pipelines.find((p) => p.id === currentPipelineId)

  const handleSavePanelConfig = async (panelForm) => {
    if (!studyId || !config?.config) return
    const merged = { ...config.config }
    Object.entries(panelForm).forEach(([k, v]) => {
      if (v !== '********') merged[k] = v
    })
    await saveStudyConfig(studyId, merged, true)
    await fetchConfig()
  }

  const handleRevealSecret = async (key) => {
    const res = await getStudyConfig(studyId, true)
    return res.config?.[key] ?? ''
  }

  const handleStart = async () => {
    if (!studyId || !canEdit) return
    setError(null)
    setStarting(true)
    try {
      await startStudyRun(studyId, { pipeline_id: currentPipelineId || undefined })
      await fetchStatus()
    } catch (e) {
      setError(e.message)
    } finally {
      setStarting(false)
    }
  }

  const validateDefinition = useCallback((nodes, edges) => {
    const errs = []
    if (!nodes?.length) errs.push('Pipeline must have at least one node.')
    const ids = new Set()
    nodes?.forEach((n) => {
      if (!n.id) errs.push('Every node must have an id.')
      else if (ids.has(n.id)) errs.push(`Duplicate node id: ${n.id}.`)
      else ids.add(n.id)
    })
    const nodeIds = new Set(nodes?.map((n) => n.id) ?? [])
    edges?.forEach((e) => {
      if (!nodeIds.has(e.source)) errs.push(`Edge references missing source node: ${e.source}.`)
      if (!nodeIds.has(e.target)) errs.push(`Edge references missing target node: ${e.target}.`)
    })
    return errs
  }, [])

  const handleSavePipeline = async () => {
    if (!studyId || !canEdit || currentPipelineId === DEFAULT_PIPELINE_ID) return
    const errs = validateDefinition(definition.nodes, definition.edges)
    if (errs.length) {
      setError(errs.join(' '))
      return
    }
    setSavingPipeline(true)
    setError(null)
    try {
      await saveStudyPipeline(studyId, currentPipelineId, {
        name: currentPipelineName,
        is_default: pipelines.find((p) => p.id === currentPipelineId)?.isDefault ?? false,
        nodes: definition.nodes,
        edges: definition.edges,
      })
      await fetchPipelines()
      toast.success('Pipeline saved.')
    } catch (e) {
      setError(e?.message ?? e?.detail ?? String(e))
    } finally {
      setSavingPipeline(false)
    }
  }

  const handleSaveAsPipeline = async () => {
    if (!studyId || !canEdit || !saveAsName.trim()) return
    setSavingPipeline(true)
    setError(null)
    try {
      const res = await createStudyPipeline(studyId, {
        name: saveAsName.trim(),
        is_default: false,
        nodes: definition.nodes,
        edges: definition.edges,
      })
      await fetchPipelines()
      setCurrentPipelineId(res.id)
      setCurrentPipelineName(saveAsName.trim())
      setSaveAsName('')
      setShowSaveAs(false)
    } catch (e) {
      setError(e.message)
    } finally {
      setSavingPipeline(false)
    }
  }

  const handleCreateNewPipeline = async () => {
    if (!studyId || !canEdit || !newPipelineName.trim()) return
    setCreatingPipeline(true)
    setError(null)
    try {
      const res = await createStudyPipeline(studyId, {
        name: newPipelineName.trim(),
        is_default: false,
        nodes: DEFAULT_PIPELINE_DEFINITION.nodes,
        edges: DEFAULT_PIPELINE_DEFINITION.edges,
      })
      await fetchPipelines()
      setCurrentPipelineId(res.id)
      setCurrentPipelineName(newPipelineName.trim())
      setNewPipelineName('')
      setShowNewPipeline(false)
    } catch (e) {
      setError(e.message)
    } finally {
      setCreatingPipeline(false)
    }
  }

  const handleCreateFromTemplate = async () => {
    if (!studyId || !canEdit || !templateName.trim() || !selectedTemplateId) return
    const template = PIPELINE_TEMPLATES.find((t) => t.id === selectedTemplateId)
    if (!template) return
    setCreatingPipeline(true)
    setError(null)
    try {
      const res = await createStudyPipeline(studyId, {
        name: templateName.trim(),
        is_default: false,
        nodes: template.nodes,
        edges: template.edges,
      })
      await fetchPipelines()
      setCurrentPipelineId(res.id)
      setCurrentPipelineName(templateName.trim())
      setTemplateName('')
      setSelectedTemplateId(null)
      setShowTemplateModal(false)
      toast.success('Pipeline created from template.')
    } catch (e) {
      setError(e.message)
    } finally {
      setCreatingPipeline(false)
    }
  }

  const handlePipelineSelect = (pipelineId) => {
    setSelectedNodeId(null)
    setCurrentPipelineId(pipelineId)
    const p = pipelines.find((x) => x.id === pipelineId)
    setCurrentPipelineName(p?.name ?? 'Default')
  }

  const handleStop = async () => {
    if (!studyId || !canEdit) return
    setStopping(true)
    try {
      await stopStudyRun(studyId)
      await fetchStatus()
    } catch (e) {
      setError(e.message)
    } finally {
      setStopping(false)
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
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Loading…</p>
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
        canEdit={canEdit}
      />
      <main className="mx-auto max-w-5xl space-y-4 p-4 md:p-6">
        <Breadcrumb
          items={[
            { label: 'Dashboard', to: '/studies' },
            { label: currentStudyName, to: `/studies/${studyId}` },
            { label: 'Pipeline Graph' },
          ]}
          className="mb-1"
        />
        <PageHeader
          title="Pipeline Graph"
          description="Edit the pipeline as a graph of components. Changes are saved per pipeline. Experimental UI."
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
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Current Pipeline</CardTitle>
            <CardDescription>Name, defaults, and size of the graph you are editing.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="text-xs font-medium text-muted-foreground">Pipeline</dt>
                <dd className="mt-1 text-sm font-medium text-foreground">{currentPipelineName || selectedPipelineMeta?.name || '—'}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-muted-foreground">Default</dt>
                <dd className="mt-1 text-sm text-foreground">{selectedPipelineMeta?.isDefault ? 'Yes' : 'No'}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-muted-foreground">Nodes</dt>
                <dd className="mt-1 text-sm tabular-nums text-foreground">{definition?.nodes?.length ?? 0}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-muted-foreground">Edges</dt>
                <dd className="mt-1 text-sm tabular-nums text-foreground">{definition?.edges?.length ?? 0}</dd>
              </div>
            </dl>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className="text-xs font-normal">Experimental</Badge>
              {streamStatus === 'connected' && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground" title="Receiving live updates">
                  <Circle className="size-2 fill-emerald-500 text-emerald-500" aria-hidden />
                  Live Updates
                </span>
              )}
              {streamStatus === 'reconnecting' && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="size-3 animate-spin" aria-hidden />
                  Reconnecting…
                </span>
              )}
            </div>
          </CardContent>
          {(pipelines.length > 0 || canEdit) && (
          <CardFooter className="flex flex-wrap items-center gap-3 border-t border-border pt-6">
          {pipelines.length > 0 && (
            <Select
              value={currentPipelineId && pipelines.some((p) => p.id === currentPipelineId) ? currentPipelineId : (pipelines[0]?.id ?? '')}
              onValueChange={handlePipelineSelect}
            >
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="Pipeline" />
              </SelectTrigger>
              <SelectContent>
                {pipelines.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                    {p.isDefault ? ' (default)' : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {canEdit && currentPipelineId && currentPipelineId !== DEFAULT_PIPELINE_ID && (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleSavePipeline}
              disabled={savingPipeline}
            >
              {savingPipeline ? 'Saving…' : 'Save pipeline'}
            </Button>
          )}
          {canEdit && (
            <>
              <Button
                variant="default"
                size="sm"
                onClick={() => setShowNewPipeline(true)}
                disabled={creatingPipeline}
                className="gap-1.5"
              >
                <Plus className="size-4" aria-hidden />
                New pipeline
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowTemplateModal(true)
                  setSelectedTemplateId(PIPELINE_TEMPLATES[0]?.id ?? null)
                  setTemplateName('')
                }}
                disabled={creatingPipeline}
              >
                From Template
              </Button>
              {showTemplateModal && (
                <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/20 p-3">
                  <p className="text-xs font-medium text-muted-foreground">New from template</p>
                  <select
                    className="rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                    value={selectedTemplateId ?? ''}
                    onChange={(e) => setSelectedTemplateId(e.target.value || null)}
                    aria-label="Template"
                  >
                    {PIPELINE_TEMPLATES.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                  {selectedTemplateId && (
                    <p className="text-xs text-muted-foreground">
                      {PIPELINE_TEMPLATES.find((t) => t.id === selectedTemplateId)?.description}
                    </p>
                  )}
                  <input
                    type="text"
                    placeholder="Pipeline name"
                    className="rounded-md border border-input bg-background px-2 py-1 text-sm w-52"
                    value={templateName}
                    onChange={(e) => setTemplateName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleCreateFromTemplate()
                      if (e.key === 'Escape') { setShowTemplateModal(false); setTemplateName(''); setSelectedTemplateId(null) }
                    }}
                  />
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleCreateFromTemplate} disabled={!templateName.trim() || !selectedTemplateId || creatingPipeline}>
                      {creatingPipeline ? 'Creating…' : 'Create'}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => { setShowTemplateModal(false); setTemplateName(''); setSelectedTemplateId(null) }}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
              {showNewPipeline && (
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="Pipeline name"
                    className="rounded-md border border-input bg-background px-2 py-1 text-sm w-44"
                    value={newPipelineName}
                    onChange={(e) => setNewPipelineName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleCreateNewPipeline()
                      if (e.key === 'Escape') { setShowNewPipeline(false); setNewPipelineName('') }
                    }}
                  />
                  <Button size="sm" onClick={handleCreateNewPipeline} disabled={!newPipelineName.trim() || creatingPipeline}>
                    {creatingPipeline ? 'Creating…' : 'Create'}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => { setShowNewPipeline(false); setNewPipelineName('') }}>
                    Cancel
                  </Button>
                </div>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowSaveAs(true)}
                disabled={savingPipeline}
              >
                Save as…
              </Button>
              {showSaveAs && (
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="New pipeline name"
                    className="rounded-md border border-input bg-background px-2 py-1 text-sm"
                    value={saveAsName}
                    onChange={(e) => setSaveAsName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleSaveAsPipeline()
                      if (e.key === 'Escape') setShowSaveAs(false)
                    }}
                  />
                  <Button size="sm" onClick={handleSaveAsPipeline} disabled={!saveAsName.trim() || savingPipeline}>
                    Create
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setShowSaveAs(false)}>
                    Cancel
                  </Button>
                </div>
              )}
            </>
          )}
          </CardFooter>
          )}
        </Card>
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <section aria-labelledby="current-step-heading" className="rounded-lg border border-border bg-card px-3 py-2">
          <h2 id="current-step-heading" className="text-sm font-medium text-muted-foreground">
            Current Step
          </h2>
          <p className="mt-0.5 text-sm text-foreground" aria-live="polite">
            {status === 'running' || status === 'completed' || status === 'failed' || status === 'stopped'
              ? currentStep || STATUS_LABELS[status] || status
              : 'Idle'}
          </p>
        </section>
        <section aria-label="Pipeline setup" className="grid gap-4 lg:grid-cols-[1fr_340px]">
          <div className="rounded-xl border border-border bg-card p-4 space-y-3">
            {canEdit && definition.nodes.length > 0 && (
              <PipelineNodePalette onAddNode={handleAddNode} editable={canEdit} />
            )}
            <PipelineFlow
              key={currentPipelineId ?? 'none'}
              status={status}
              currentStep={currentStep}
              selectedNodeId={selectedNodeId}
              onNodeClick={setSelectedNodeId}
              definition={definition.nodes.length ? definition : null}
              onDefinitionChange={setDefinition}
              editable={canEdit}
            />
          </div>
          <div className="lg:min-w-0">
            <PipelineNodeConfigPanel
              studyId={studyId}
              nodeId={selectedNodeId}
              nodeType={definition.nodes?.find((n) => n.id === selectedNodeId)?.type}
              config={config?.config}
              onSave={handleSavePanelConfig}
              onRevealSecret={handleRevealSecret}
              readOnly={!canEdit}
            />
          </div>
        </section>
      </main>
    </div>
  )
}
