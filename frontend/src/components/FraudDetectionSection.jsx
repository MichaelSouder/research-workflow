import { useState } from 'react'
import { FRAUD_KEYS, FRAUD_LABELS } from '../constants'

export default function FraudDetectionSection({ form, onFraudChange }) {
  const [open, setOpen] = useState(false)
  const handleToggle = (key, checked) => onFraudChange(key, checked ? 'true' : 'false')
  return (
    <section className="rounded-xl border border-slate-700 bg-slate-800/50">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-slate-300 hover:bg-slate-700/50"
      >
        Fraud detection
        <span className="text-slate-500">{open ? '▼' : '▶'}</span>
      </button>
      {open && (
        <div className="border-t border-slate-700 p-4">
          <p className="mb-4 text-xs text-slate-500">
            When enabled, the pipeline runs fraud checks and skips responses flagged by the selected checks. Save in Settings to persist.
          </p>
          <div className="space-y-4">
            {FRAUD_KEYS.map((key) => (
              <label
                key={key}
                className="flex cursor-pointer items-center gap-3 rounded border border-slate-600 bg-slate-700/30 px-3 py-2 text-sm text-slate-200"
              >
                <input
                  type="checkbox"
                  checked={(form[key] ?? 'true') === 'true'}
                  onChange={(e) => handleToggle(key, e.target.checked)}
                  className="h-4 w-4 rounded border-slate-500"
                />
                <span>{FRAUD_LABELS[key] ?? key}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
