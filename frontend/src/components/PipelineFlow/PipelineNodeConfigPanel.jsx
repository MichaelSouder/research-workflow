import { useState, useEffect } from 'react'
import { NODE_CONFIG, isSecretKey, defaultKeyLabel } from './componentConfig'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import GridStudyModal from '../GridStudyModal'
import BoxFolderModal from '../BoxFolderModal'

/** True if this node type has any settings fields in the panel. */
function nodeMetaHasConfigurableFields(meta) {
  if (!meta) return false
  if (meta.sections?.some((s) => (s.keys || []).length > 0)) return true
  const keys = meta.keys
  return Array.isArray(keys) && keys.length > 0
}

/**
 * Resolve which NODE_CONFIG entry to use. Saved pipelines often use type "stage" for every
 * node; the real component is the node id (qualtrics, process, grid, box, …).
 */
function resolveConfigKey(selectedNodeType, nodeId, baseNodeId) {
  const tryKey = (k) => {
    if (!k || k === 'stage') return null
    const m = NODE_CONFIG[k]
    return nodeMetaHasConfigurableFields(m) ? k : null
  }
  return (
    tryKey(selectedNodeType) ||
    tryKey(nodeId) ||
    tryKey(baseNodeId) ||
    (selectedNodeType && selectedNodeType !== 'stage' ? selectedNodeType : null) ||
    baseNodeId ||
    nodeId ||
    null
  )
}

export default function PipelineNodeConfigPanel({
  nodeId,
  nodeType: selectedNodeType = null,
  config,
  onSave,
  onRevealSecret,
  readOnly = false,
  studyId = null,
}) {
  const baseNodeId = nodeId?.replace(/_\d+$/, '') ?? null
  const configKey = nodeId ? resolveConfigKey(selectedNodeType, nodeId, baseNodeId) : null
  const nodeMeta = configKey ? NODE_CONFIG[configKey] ?? NODE_CONFIG[baseNodeId] ?? NODE_CONFIG[nodeId] : null
  const [form, setForm] = useState({})
  const [showSecrets, setShowSecrets] = useState({})
  const [saving, setSaving] = useState(false)
  const [showGridModal, setShowGridModal] = useState(false)
  const [showBoxModal, setShowBoxModal] = useState(false)

  useEffect(() => {
    if (!nodeMeta) return
    const cfg = config || {}
    const keys = nodeMeta.keys || []
    const next = {}
    keys.forEach((k) => {
      next[k] = cfg[k] ?? ''
    })
    setForm(next)
  }, [nodeId, config, nodeMeta])

  const handleChange = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    if (!onSave || readOnly) return
    setSaving(true)
    try {
      await onSave(form)
    } finally {
      setSaving(false)
    }
  }

  if (!nodeId || !nodeMeta) {
    return (
      <Card className="w-full border-border bg-card">
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <p className="text-sm text-muted-foreground">Click a node to configure it.</p>
        </CardContent>
      </Card>
    )
  }

  const isBooleanKey = (k) =>
    k === 'DUPLICATE_SKIP_ENABLED' ||
    k === 'FRAUD_ENABLED' ||
    k === 'FRAUD_SPEED' ||
    k === 'FRAUD_DUPLICATE_IP' ||
    k === 'FRAUD_STRAIGHTLINING' ||
    k === 'FRAUD_INCOMPLETE'

  const renderField = (key, labelOverride = null) => {
    const label = labelOverride ?? defaultKeyLabel(key)
    const isSecret = isSecretKey(key)
    const value = form[key]
    const isMasked = value === '********'
    const isBoolean = isBooleanKey(key)

    if (isBoolean) {
      return (
        <div key={key} className="flex items-center justify-between gap-2">
          <label className="text-xs font-medium text-muted-foreground">{label}</label>
          <input
            type="checkbox"
            checked={(value ?? 'true') === 'true'}
            onChange={(e) => handleChange(key, e.target.checked ? 'true' : 'false')}
            readOnly={readOnly}
            disabled={readOnly}
            className="h-4 w-4 rounded border-input"
          />
        </div>
      )
    }

    return (
      <div key={key} className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">{label}</label>
        <div className="flex gap-2">
          <input
            type={showSecrets[key] ? 'text' : isSecret ? 'password' : 'text'}
            value={isMasked ? '********' : value ?? ''}
            onChange={(e) => handleChange(key, e.target.value)}
            readOnly={readOnly}
            disabled={readOnly}
            placeholder={
              isSecret && !isMasked ? 'Leave empty to use script default' : ''
            }
            className="min-w-0 flex-1 rounded border border-input bg-background px-2 py-1.5 text-sm"
          />
          {key === 'GRID_STUDY_ID' && studyId && !readOnly && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={() => setShowGridModal(true)}
            >
              Browse
            </Button>
          )}
          {key === 'BOX_ROOT_FOLDER_ID' && studyId && !readOnly && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={() => setShowBoxModal(true)}
            >
              Browse
            </Button>
          )}
          {isSecret && !readOnly && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={async () => {
                if (showSecrets[key]) {
                  setShowSecrets((s) => ({ ...s, [key]: false }))
                  handleChange(key, '********')
                } else if (onRevealSecret) {
                  try {
                    const v = await onRevealSecret(key)
                    handleChange(key, v ?? '')
                    setShowSecrets((s) => ({ ...s, [key]: true }))
                  } catch {
                    setShowSecrets((s) => ({ ...s, [key]: true }))
                  }
                } else {
                  setShowSecrets((s) => ({ ...s, [key]: !s[key] }))
                }
              }}
            >
              {showSecrets[key] ? 'Hide' : 'Show'}
            </Button>
          )}
        </div>
      </div>
    )
  }

  const renderSection = (section) => {
    const labels = section.labels || {}
    const isProcessDuplicateSection =
      (baseNodeId === 'process' || nodeId === 'process') && section.label === 'Duplicate Skip'
    const keys =
      isProcessDuplicateSection && studyId
        ? section.keys.filter((k) => k !== 'PROCESSED_IDS_PATH')
        : section.keys
    return (
      <div key={section.label} className="space-y-2">
        <h4 className="text-sm font-medium text-foreground">{section.label}</h4>
        {isProcessDuplicateSection && studyId && (
          <p className="text-xs text-muted-foreground">
            Processed response IDs for this study are stored in the database; no file path is used.
          </p>
        )}
        <div className="space-y-2 pl-0">
          {keys.map((key) => renderField(key, labels[key]))}
        </div>
      </div>
    )
  }

  return (
    <>
    <Card className="w-full border-border bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{nodeMeta.label}</CardTitle>
        {nodeMeta.description && (
          <CardDescription className="text-xs">{nodeMeta.description}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {nodeMeta.sections ? (
          nodeMeta.sections.map(renderSection)
        ) : (
          <div className="space-y-3">
            {nodeMeta.keys.map((key) => renderField(key))}
          </div>
        )}
        {!readOnly && (
          <Button
            type="button"
            size="sm"
            onClick={handleSave}
            disabled={saving}
            className="w-full"
          >
            {saving ? 'Saving…' : 'Save'}
          </Button>
        )}
      </CardContent>
    </Card>
    {showGridModal && (
      <GridStudyModal
        studyId={studyId}
        onSelect={(id) => {
          handleChange('GRID_STUDY_ID', id)
          setShowGridModal(false)
        }}
        onClose={() => setShowGridModal(false)}
      />
    )}
    {showBoxModal && (
      <BoxFolderModal
        studyId={studyId}
        onSelect={(id) => {
          handleChange('BOX_ROOT_FOLDER_ID', id)
          setShowBoxModal(false)
        }}
        onClose={() => setShowBoxModal(false)}
      />
    )}
  </>
  )
}
