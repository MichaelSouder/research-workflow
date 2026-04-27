import { useState, useEffect } from 'react'
import { getGridStudies, getStudyGridStudies } from '../api'

export default function GridStudyModal({ onSelect, onClose, studyId = null }) {
  const [studies, setStudies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    const fetchStudies = studyId ? getStudyGridStudies(studyId) : getGridStudies()
    fetchStudies
      .then((data) => {
        if (!cancelled) setStudies(data.studies || [])
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e.message)
          setStudies([])
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [studyId])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="max-h-[80vh] w-full max-w-md rounded-xl border border-slate-600 bg-slate-800 p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-3 text-sm font-medium text-slate-200">Select Grid study</h3>
        {error && <p className="mb-2 text-sm text-red-400">{error}</p>}
        {loading ? (
          <p className="text-sm text-slate-500">Loading studies…</p>
        ) : (
          <ul className="max-h-64 space-y-1 overflow-y-auto">
            {studies.map((study) => (
              <li
                key={study.id}
                className="flex items-center justify-between gap-2 rounded border border-slate-600 bg-slate-700/50 px-2 py-1.5 text-sm text-slate-200"
              >
                <span className="min-w-0 truncate">{study.name}</span>
                <button
                  type="button"
                  onClick={() => { onSelect(study.id); onClose() }}
                  className="rounded bg-emerald-600 px-2 py-0.5 text-xs text-white hover:bg-emerald-500"
                >
                  Select
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-slate-600 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-500"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
