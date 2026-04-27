import { useState, useEffect, useCallback } from 'react'
import { FRAUD_KEYS, FRAUD_LABELS, TAB_KEYS } from '../constants'
import { getStudyBoxConfigStatus, putStudyBoxConfig } from '../api'
import BoxFolderModal from './BoxFolderModal'
import GridStudyModal from './GridStudyModal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  SCHEDULE_PRESETS,
  WEEKDAY_OPTIONS,
  COMMON_TIMEZONES,
  parseCronToPreset,
  presetToCron,
  describeSchedule,
} from '../lib/scheduleHelpers'

export default function Settings({ config, onSave, saving, onFormChange, onRevealSecret, readOnly = false, studyId = null }) {
  const [open, setOpen] = useState(false)
  const [activeTab, setActiveTab] = useState(TAB_KEYS[0]?.id ?? 'qualtrics')
  const [form, setForm] = useState({})
  const [persist, setPersist] = useState(false)
  const [showSecrets, setShowSecrets] = useState({})
  const [boxFolderModal, setBoxFolderModal] = useState(false)
  const [gridStudyModal, setGridStudyModal] = useState(false)
  const [boxConfigConfigured, setBoxConfigConfigured] = useState(false)
  const [boxConfigPaste, setBoxConfigPaste] = useState('')
  const [boxConfigSaving, setBoxConfigSaving] = useState(false)
  const [boxConfigError, setBoxConfigError] = useState(null)

  useEffect(() => {
    if (config?.config) setForm(config.config)
  }, [config?.config])

  useEffect(() => {
    onFormChange?.(form)
  }, [form, onFormChange])

  const fetchBoxConfigStatus = useCallback(async () => {
    if (!studyId) return
    try {
      const res = await getStudyBoxConfigStatus(studyId)
      setBoxConfigConfigured(res.configured === true)
    } catch { /* ignore */ }
  }, [studyId])

  useEffect(() => {
    fetchBoxConfigStatus()
  }, [fetchBoxConfigStatus])

  const keys = config?.keys || Object.keys(form)
  const keysForTab = (tabId) => {
    const tab = TAB_KEYS.find((t) => t.id === tabId)
    if (!tab) return []
    let k = tab.keys.filter((key) => keys.includes(key))
    if (studyId && tabId === 'box') k = k.filter((key) => key !== 'BOX_CONFIG_PATH')
    if (studyId && tabId === 'processing') k = k.filter((key) => key !== 'PROCESSED_IDS_PATH')
    return k
  }
  const handleChange = (key, value) => {
    if (readOnly) return
    setForm((f) => ({ ...f, [key]: value }))
  }
  const handleSave = () => onSave(form, persist)

  const renderField = (key) => (
    <div key={key} className="flex flex-col gap-1">
      <label className="text-xs font-medium text-muted-foreground">{key}</label>
      <div className="flex gap-2">
        <Input
          type={showSecrets[key] ? 'text' : 'password'}
          value={form[key] === '********' ? '********' : (form[key] ?? '')}
          onChange={(e) => handleChange(key, e.target.value)}
          readOnly={readOnly}
          disabled={readOnly}
          placeholder={
            form[key] === '********'
              ? ''
              : key.includes('TOKEN') || key.includes('SECRET')
                ? 'Leave empty to use script default'
                : ''
          }
          className="min-w-0 flex-1 font-mono text-sm"
        />
        {(key.includes('TOKEN') || key.includes('SECRET')) && !readOnly && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="shrink-0 text-xs"
            onClick={async () => {
              if (showSecrets[key]) {
                setShowSecrets((s) => ({ ...s, [key]: false }))
                handleChange(key, '********')
              } else if (onRevealSecret) {
                try {
                  const value = await onRevealSecret(key)
                  handleChange(key, value ?? '')
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

  const handleSaveBoxConfig = async () => {
    if (!studyId || readOnly) return
    setBoxConfigError(null)
    let obj
    try {
      obj = boxConfigPaste.trim() ? JSON.parse(boxConfigPaste) : {}
    } catch (e) {
      setBoxConfigError('Invalid JSON. Paste valid Box JWT config JSON.')
      return
    }
    setBoxConfigSaving(true)
    try {
      await putStudyBoxConfig(studyId, obj)
      setBoxConfigPaste('')
      await fetchBoxConfigStatus()
    } catch (e) {
      setBoxConfigError(e?.message || 'Failed to save.')
    } finally {
      setBoxConfigSaving(false)
    }
  }

  const handleBoxConfigFile = (e) => {
    const file = e.target?.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const text = reader.result
        if (typeof text === 'string') JSON.parse(text)
        setBoxConfigPaste(text)
        setBoxConfigError(null)
      } catch {
        setBoxConfigError('File is not valid JSON.')
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  const renderTabPanel = (tabId) => {
    const tab = TAB_KEYS.find((t) => t.id === tabId)
    if (!tab) return null
    const tabKeys = tab.id === 'box' || tab.id === 'processing' ? keysForTab(tab.id) : tab.keys.filter((k) => keys.includes(k))

    if (tab.id === 'box') {
      return (
        <div className="space-y-3">
          {!studyId && tabKeys.includes('BOX_CONFIG_PATH') && (
            <div className="rounded-lg border border-border bg-muted/40 p-3">
              {renderField('BOX_CONFIG_PATH')}
            </div>
          )}
          {studyId && (
            <div className="rounded-lg border border-border bg-muted/40 p-3">
              <label className="mb-2 block text-sm font-medium text-foreground">
                Box config (stored in database)
              </label>
              <p className="mb-2 text-xs text-muted-foreground">
                {boxConfigConfigured ? 'Box config is set for this study.' : 'No Box config stored. Upload or paste JWT config JSON below.'}
              </p>
              {!readOnly && (
                <>
                  <div className="flex flex-col gap-2">
                    <input
                      type="file"
                      accept=".json,application/json"
                      onChange={handleBoxConfigFile}
                      className="text-xs text-muted-foreground file:mr-2 file:rounded file:border-0 file:bg-secondary file:px-2 file:py-1 file:text-foreground"
                    />
                    <textarea
                      value={boxConfigPaste}
                      onChange={(e) => { setBoxConfigPaste(e.target.value); setBoxConfigError(null) }}
                      placeholder='Or paste Box JWT config JSON (e.g. {"boxAppSettings": {...}})'
                      rows={4}
                      className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground placeholder:text-muted-foreground font-mono"
                    />
                    {boxConfigError && <p className="text-xs text-destructive">{boxConfigError}</p>}
                    <button
                      type="button"
                      onClick={handleSaveBoxConfig}
                      disabled={boxConfigSaving}
                      className="w-fit rounded bg-secondary px-3 py-1.5 text-sm text-foreground hover:bg-secondary/80 disabled:opacity-50"
                    >
                      {boxConfigSaving ? 'Saving…' : 'Save Box config'}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
          <div className="rounded-lg border border-border bg-muted/40 p-3">
            <label className="mb-2 block text-sm font-medium text-foreground">
              Box folder to save video folders to
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={form.BOX_ROOT_FOLDER_ID === '********' ? '' : (form.BOX_ROOT_FOLDER_ID ?? '')}
                onChange={(e) => handleChange('BOX_ROOT_FOLDER_ID', e.target.value)}
                placeholder="e.g. 334546874262"
                readOnly={readOnly}
                disabled={readOnly}
                className="min-w-0 flex-1 rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground placeholder:text-muted-foreground"
              />
              {!readOnly && (
                <button
                  type="button"
                  onClick={() => setBoxFolderModal(true)}
                  className="shrink-0 rounded bg-secondary px-3 py-1.5 text-sm text-foreground hover:bg-secondary/80"
                >
                  Browse Box folders
                </button>
              )}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              All pipeline video folders will be created under this folder.
            </p>
          </div>
          {boxFolderModal && (
            <BoxFolderModal
              studyId={studyId}
              onSelect={(id) => handleChange('BOX_ROOT_FOLDER_ID', id)}
              onClose={() => setBoxFolderModal(false)}
            />
          )}
        </div>
      )
    }

    if (tab.id === 'grid') {
      return (
        <div className="space-y-3">
          {tabKeys.filter((k) => k !== 'GRID_STUDY_ID').map((k) => (
            <div key={k} className="rounded-lg border border-border bg-muted/40 p-3">
              {renderField(k)}
            </div>
          ))}
          <div className="rounded-lg border border-border bg-muted/40 p-3">
            <label className="mb-2 block text-sm font-medium text-foreground">Grid study ID</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={form.GRID_STUDY_ID === '********' ? '' : (form.GRID_STUDY_ID ?? '')}
                onChange={(e) => handleChange('GRID_STUDY_ID', e.target.value)}
                placeholder="e.g. 372"
                readOnly={readOnly}
                disabled={readOnly}
                className="min-w-0 flex-1 rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground placeholder:text-muted-foreground"
              />
              {!readOnly && (
                <button
                  type="button"
                  onClick={() => setGridStudyModal(true)}
                  className="shrink-0 rounded bg-secondary px-3 py-1.5 text-sm text-foreground hover:bg-secondary/80"
                >
                  Browse
                </button>
              )}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Study used for subjects and events in the pipeline.
            </p>
          </div>
          {gridStudyModal && (
            <GridStudyModal
              studyId={studyId}
              onSelect={(id) => handleChange('GRID_STUDY_ID', id)}
              onClose={() => setGridStudyModal(false)}
            />
          )}
        </div>
      )
    }

    if (tab.id === 'qualtrics') {
      return (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">Survey and data center for export.</p>
          {tabKeys.map((k) => renderField(k))}
        </div>
      )
    }

    if (tab.id === 'schedule') {
      const cron = (form.SCHEDULE_CRON ?? '').trim() || '0 9 * * *'
      const tz = (form.SCHEDULE_TIMEZONE ?? '').trim() || 'America/Chicago'
      const parsed = parseCronToPreset(cron)
      const effectivePreset = parsed.preset === 'custom' ? 'daily' : parsed.preset
      const timeValue = `${String(parsed.hour).padStart(2, '0')}:${String(parsed.minute).padStart(2, '0')}`
      const tzInList = COMMON_TIMEZONES.includes(tz)
      const handlePresetChange = (preset) => {
        const day = preset === 'weekly' ? (parsed.dayOfWeek ?? 1) : null
        handleChange('SCHEDULE_CRON', presetToCron(preset, parsed.hour, parsed.minute, day))
      }
      const handleTimeChange = (hhmm) => {
        const [h, m] = hhmm.split(':').map(Number)
        const day = effectivePreset === 'weekly' ? (parsed.dayOfWeek ?? 1) : null
        handleChange('SCHEDULE_CRON', presetToCron(effectivePreset, h, m, day))
      }
      const handleDayChange = (dayOfWeek) => {
        handleChange('SCHEDULE_CRON', presetToCron(effectivePreset, parsed.hour, parsed.minute, dayOfWeek))
      }
      return (
        <div className="space-y-4">
          <p className="text-xs text-muted-foreground">
            Run the pipeline automatically on a schedule. When a run is already in progress, the scheduled run is skipped.
          </p>
          <label className="flex cursor-pointer items-center gap-3 rounded border border-border bg-muted/40 px-3 py-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={(form.SCHEDULE_ENABLED ?? 'false') === 'true'}
              onChange={(e) => handleChange('SCHEDULE_ENABLED', e.target.checked ? 'true' : 'false')}
              className="h-4 w-4 rounded border-input"
              disabled={readOnly}
            />
            <span>Enable scheduled runs</span>
          </label>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Frequency</label>
            <select
              value={effectivePreset}
              onChange={(e) => handlePresetChange(e.target.value)}
              disabled={readOnly}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              {SCHEDULE_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-muted-foreground">Time</label>
              <input
                type="time"
                value={timeValue}
                onChange={(e) => handleTimeChange(e.target.value)}
                disabled={readOnly}
                className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
              />
            </div>
            {effectivePreset === 'weekly' && (
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-muted-foreground">Day</label>
                <select
                  value={parsed.dayOfWeek ?? 1}
                  onChange={(e) => handleDayChange(Number(e.target.value))}
                  disabled={readOnly}
                  className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
                >
                  {WEEKDAY_OPTIONS.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">Time zone</label>
            <select
              value={tzInList ? tz : '__other__'}
              onChange={(e) => {
                if (e.target.value !== '__other__') handleChange('SCHEDULE_TIMEZONE', e.target.value)
              }}
              disabled={readOnly}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              {COMMON_TIMEZONES.map((z) => (
                <option key={z} value={z}>
                  {z}
                </option>
              ))}
              <option value="__other__">Other…</option>
            </select>
            {!tzInList && (
              <input
                type="text"
                value={tz}
                onChange={(e) => handleChange('SCHEDULE_TIMEZONE', e.target.value)}
                placeholder="e.g. America/Chicago"
                disabled={readOnly}
                className="mt-1 rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground placeholder:text-muted-foreground"
              />
            )}
          </div>

          <p className="rounded border border-border/50 bg-muted/30 px-3 py-2 text-sm text-foreground" role="status">
            {describeSchedule(cron, tz)}
          </p>
        </div>
      )
    }

    if (tab.id === 'processing') {
      return (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            Skip responses already processed in a prior run (stored by response ID). When disabled, all records are processed.
          </p>
          {studyId && (
            <p className="text-xs text-muted-foreground">
              For this study, processed IDs are stored in the database (no file path needed).
            </p>
          )}
          <label className="flex cursor-pointer items-center gap-3 rounded border border-border bg-muted/40 px-3 py-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={(form.DUPLICATE_SKIP_ENABLED ?? 'true') === 'true'}
              onChange={(e) => handleChange('DUPLICATE_SKIP_ENABLED', e.target.checked ? 'true' : 'false')}
              className="h-4 w-4 rounded border-input"
            />
            <span>Skip already-processed responses (duplicate detection)</span>
          </label>
          {!studyId && (
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">PROCESSED_IDS_PATH</label>
              <input
                type="text"
                value={form.PROCESSED_IDS_PATH ?? ''}
                onChange={(e) => handleChange('PROCESSED_IDS_PATH', e.target.value)}
                placeholder="Leave empty for default (backend/workspace/processed_response_ids.json)"
                className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground placeholder:text-muted-foreground"
              />
            </div>
          )}
        </div>
      )
    }

    if (tab.id === 'fraud') {
      return (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            When enabled, the pipeline runs fraud checks and skips responses flagged by the selected checks. Save to persist.
          </p>
          <div className="space-y-4">
            {FRAUD_KEYS.map((key) => (
              <label
                key={key}
                className="flex cursor-pointer items-center gap-3 rounded border border-border bg-muted/40 px-3 py-2 text-sm text-foreground"
              >
                <input
                  type="checkbox"
                  checked={(form[key] ?? 'true') === 'true'}
                  onChange={(e) => handleChange(key, e.target.checked ? 'true' : 'false')}
                  className="h-4 w-4 rounded border-input"
                />
                <span>{FRAUD_LABELS[key] ?? key}</span>
              </label>
            ))}
          </div>
        </div>
      )
    }

    // generic key/value inputs for any tab that doesn't have custom UI
    return <div className="space-y-3">{tabKeys.map((k) => renderField(k))}</div>
  }

  return (
    <section className="rounded-xl border border-border bg-card" aria-labelledby="connections-heading">
      <h2 id="connections-heading" className="sr-only">Connections & settings</h2>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-foreground hover:bg-muted/50 rounded-t-xl transition-colors"
        aria-expanded={open}
      >
        Connections & settings
        <span className="text-muted-foreground" aria-hidden>{open ? '▼' : '▶'}</span>
      </button>
      {open && (
        <div className="border-t border-border p-4">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList variant="line" className="mb-4 h-auto min-h-9 w-full flex-wrap justify-start gap-1" aria-label="Configuration sections">
              {TAB_KEYS.map((t) => (
                <TabsTrigger key={t.id} value={t.id}>
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>
            {TAB_KEYS.map((t) => (
              <TabsContent key={t.id} value={t.id} className="min-h-[120px] outline-none">
                {renderTabPanel(t.id)}
              </TabsContent>
            ))}
          </Tabs>
          {!readOnly && (
            <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-border pt-4">
              {!studyId && (
                <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={persist}
                    onChange={(e) => setPersist(e.target.checked)}
                    className="h-4 w-4 rounded border-input"
                  />
                  Save to file (persist across restarts)
                </label>
              )}
              {studyId && <span className="text-xs text-muted-foreground">Config is saved to the database.</span>}
              <Button onClick={handleSave} disabled={saving} type="button">
                {saving ? 'Saving…' : 'Save config'}
              </Button>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
