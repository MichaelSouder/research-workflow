/** Shared constants for pipeline UI */

export const POLL_INTERVAL_MS = 1500

export const STATUS_LABELS = {
  idle: 'Idle',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  stopped: 'Stopped',
}

export const STATUS_COLORS = {
  idle: 'bg-slate-500',
  running: 'bg-amber-500 animate-pulse',
  completed: 'bg-emerald-600',
  failed: 'bg-red-600',
  stopped: 'bg-amber-600',
}

export const FRAUD_KEYS = [
  'FRAUD_ENABLED',
  'FRAUD_SPEED',
  'FRAUD_DUPLICATE_IP',
  'FRAUD_STRAIGHTLINING',
  'FRAUD_INCOMPLETE',
]

export const FRAUD_LABELS = {
  FRAUD_ENABLED: 'Enable fraud detection in pipeline',
  FRAUD_SPEED: 'Flag suspiciously fast completions (speed)',
  FRAUD_DUPLICATE_IP: 'Flag duplicate IP addresses',
  FRAUD_STRAIGHTLINING: 'Flag straightlining (same answer repeated)',
  FRAUD_INCOMPLETE: 'Flag incomplete responses',
}

/** Tab id → config key groups for Settings. Same form state and Save apply to all tabs. */
export const TAB_KEYS = [
  { id: 'qualtrics', label: 'Qualtrics', keys: ['QUALTRICS_API_TOKEN', 'QUALTRICS_SURVEY_ID', 'QUALTRICS_DATA_CENTER'] },
  { id: 'grid', label: 'Grid', keys: ['GRID_API_TOKEN', 'GRID_STUDY_ID'] },
  { id: 'box', label: 'Box', keys: ['BOX_ROOT_FOLDER_ID', 'BOX_CONFIG_PATH'] },
  { id: 'processing', label: 'Processing', keys: ['DUPLICATE_SKIP_ENABLED', 'PROCESSED_IDS_PATH'] },
  { id: 'schedule', label: 'Schedule', keys: ['SCHEDULE_ENABLED', 'SCHEDULE_CRON', 'SCHEDULE_TIMEZONE'] },
  { id: 'fraud', label: 'Fraud Detection', keys: ['FRAUD_ENABLED', 'FRAUD_SPEED', 'FRAUD_DUPLICATE_IP', 'FRAUD_STRAIGHTLINING', 'FRAUD_INCOMPLETE'] },
]

/** Distribution config keys (editable on the Distribution page). */
export const DISTRIBUTION_CONFIG_KEYS = [
  'QUALTRICS_DIRECTORY_ID',
  'QUALTRICS_MAILING_LIST_ID',
  'QUALTRICS_LIBRARY_ID',
  'QUALTRICS_MESSAGE_ID_SMS',
  'QUALTRICS_MESSAGE_ID_EMAIL',
  'QUALTRICS_CONTACT_METHOD',
  'QUALTRICS_DISTRIBUTION_TIMEZONE',
  'QUALTRICS_DISTRIBUTION_TIME_SLOTS',
  'QUALTRICS_DISTRIBUTION_EXPIRE_MINUTES',
]

/** Short labels for distribution config keys (Distribution page). */
export const DISTRIBUTION_CONFIG_LABELS = {
  QUALTRICS_DIRECTORY_ID: 'Directory ID',
  QUALTRICS_MAILING_LIST_ID: 'Mailing list ID',
  QUALTRICS_LIBRARY_ID: 'Message library ID',
  QUALTRICS_MESSAGE_ID_SMS: 'SMS message ID',
  QUALTRICS_MESSAGE_ID_EMAIL: 'Email message ID',
  QUALTRICS_CONTACT_METHOD: 'Contact method',
  QUALTRICS_DISTRIBUTION_TIMEZONE: 'Distribution time zone',
  QUALTRICS_DISTRIBUTION_TIME_SLOTS: 'Time slots (JSON, e.g. [[800,900],[1200,1300]])',
  QUALTRICS_DISTRIBUTION_EXPIRE_MINUTES: 'Link expiration (minutes)',
}

/** Contact method options for distribution (SMS / email). */
export const DISTRIBUTION_CONTACT_METHODS = [
  { value: 'email', label: 'Email' },
  { value: 'sms', label: 'SMS' },
]

export const HELP_TABS = [
  { id: 'guides', label: 'Guides' },
  { id: 'troubleshooting', label: 'Troubleshooting' },
]

/** Pipeline stages (left to right). Used by PipelineStrip and step→stage mapping. */
export const STAGE_ORDER = ['qualtrics', 'process', 'grid', 'box']

export const STAGE_LABELS = {
  qualtrics: 'Qualtrics',
  process: 'Process',
  grid: 'Grid',
  box: 'Box',
}

/** Map backend currentStep string to pipeline stage id. */
export const STEP_TO_STAGE = {
  'Starting pipeline': 'process',
  'Qualtrics export': 'qualtrics',
  'Retrieving videos': 'process',
  'Grid / subjects': 'grid',
  'Box upload': 'box',
  'Completed': 'box', // all done; show last stage as complete
}

/**
 * Stage state for pipeline strip and graph: pending | in_progress | done | error.
 * @param {string} stageId - Stage id (qualtrics, process, grid, box)
 * @param {number} stageIndex - Index in STAGE_ORDER
 * @param {number} currentStageIndex - Index of current stage (-1 if completed or idle)
 * @param {string} status - Run status (idle, running, completed, failed, stopped)
 */
export function getStageState(stageId, stageIndex, currentStageIndex, status) {
  if (status === 'completed') return 'done'
  if (status === 'failed' || status === 'stopped') {
    if (stageIndex < currentStageIndex) return 'done'
    if (stageIndex === currentStageIndex) return 'error'
    return 'pending'
  }
  if (status === 'running') {
    if (stageIndex < currentStageIndex) return 'done'
    if (stageIndex === currentStageIndex) return 'in_progress'
    return 'pending'
  }
  return 'pending'
}

/** Map step text (e.g. from activity) to stage label for display. */
export function getStageLabelForStep(step) {
  if (!step || typeof step !== 'string') return null
  const stageId = STEP_TO_STAGE[step]
  return stageId ? STAGE_LABELS[stageId] : null
}
