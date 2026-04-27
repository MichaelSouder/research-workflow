/**
 * Pipeline graph node types and config. Used by palette (categories) and config panel.
 */

import { FRAUD_KEYS, FRAUD_LABELS } from '../../constants'

/** Node IDs in the pipeline graph (must match STAGE_ORDER for default strip). */
export const PIPELINE_NODE_IDS = ['qualtrics', 'process', 'grid', 'box']

/**
 * Categories for the node palette. Each has id, label, and node types in order.
 */
export const NODE_CATEGORIES = [
  {
    id: 'sources',
    label: 'Sources',
    nodeTypes: ['qualtrics', 'file_import'],
  },
  {
    id: 'processing',
    label: 'Processing',
    nodeTypes: ['process', 'normalize', 'duplicate_skip', 'fraud'],
  },
  {
    id: 'sinks',
    label: 'Sinks',
    nodeTypes: ['grid', 'box'],
  },
  {
    id: 'integration',
    label: 'Integration',
    nodeTypes: ['webhook', 'http_call'],
  },
]

/**
 * Config key groups per node type. Each entry: { label, description?, keys | sections }.
 */
export const NODE_CONFIG = {
  qualtrics: {
    label: 'Qualtrics',
    description: 'Export survey responses and media.',
    keys: [
      'QUALTRICS_API_TOKEN',
      'QUALTRICS_SURVEY_ID',
      'QUALTRICS_DATA_CENTER',
    ],
  },
  file_import: {
    label: 'File import',
    description: 'Import responses or media from a file (e.g. CSV, JSON).',
    keys: ['FILE_IMPORT_PATH', 'FILE_IMPORT_FORMAT'],
  },
  process: {
    label: 'Process',
    description: 'Normalize, duplicate skip, and fraud detection.',
    sections: [
      {
        label: 'Duplicate Skip',
        keys: ['DUPLICATE_SKIP_ENABLED', 'PROCESSED_IDS_PATH'],
      },
      {
        label: 'Fraud detection',
        keys: FRAUD_KEYS,
        labels: FRAUD_LABELS,
      },
    ],
    get keys() {
      return this.sections.flatMap((s) => s.keys)
    },
  },
  normalize: {
    label: 'Normalize',
    description: 'Normalize field names and completion flags.',
    keys: [],
  },
  duplicate_skip: {
    label: 'Duplicate Skip',
    description: 'Skip responses already processed (by response ID).',
    keys: ['DUPLICATE_SKIP_ENABLED', 'PROCESSED_IDS_PATH'],
  },
  fraud: {
    label: 'Fraud detection',
    description: 'Flag or filter suspicious responses.',
    keys: FRAUD_KEYS,
    labels: FRAUD_LABELS,
  },
  grid: {
    label: 'Grid',
    description: 'Send subjects and events to Grid.',
    keys: ['GRID_API_TOKEN', 'GRID_STUDY_ID'],
  },
  box: {
    label: 'Box',
    description: 'Upload files to Box folders.',
    keys: ['BOX_ROOT_FOLDER_ID', 'BOX_CONFIG_PATH'],
  },
  webhook: {
    label: 'Webhook',
    description: 'Send data to an external URL (POST).',
    keys: ['WEBHOOK_URL', 'WEBHOOK_METHOD'],
  },
  http_call: {
    label: 'HTTP call',
    description: 'Call an external API (GET/POST).',
    keys: ['HTTP_CALL_URL', 'HTTP_CALL_METHOD', 'HTTP_CALL_HEADERS'],
  },
  stage: {
    label: 'Stage',
    description: 'Generic pipeline stage.',
    keys: [],
  },
}

/** Keys that are secret (masked in UI unless revealed). */
export const SECRET_KEYS = ['QUALTRICS_API_TOKEN', 'GRID_API_TOKEN', 'BOX_CLIENT_SECRET']

export function isSecretKey(key) {
  return SECRET_KEYS.includes(key) || key.includes('TOKEN') || key.includes('SECRET')
}

/** Human-friendly label for a config key when no specific label is provided. */
export function defaultKeyLabel(key) {
  return key
    .replace(/_/g, ' ')
    .replace(/\b(api|id|path|url)\b/gi, (m) => m.toLowerCase())
}
