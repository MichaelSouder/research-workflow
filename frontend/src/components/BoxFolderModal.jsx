import { useState, useEffect } from 'react'
import { getBoxFolders, getStudyBoxFolders } from '../api'

export default function BoxFolderModal({ onSelect, onClose, studyId = null }) {
  const [folders, setFolders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [breadcrumb, setBreadcrumb] = useState([{ id: '0', name: 'All Files' }])

  const currentRoot = breadcrumb[breadcrumb.length - 1]?.id ?? '0'

  const loadFolders = async (rootId) => {
    setLoading(true)
    setError(null)
    try {
      const data = studyId
        ? await getStudyBoxFolders(studyId, rootId)
        : await getBoxFolders(rootId)
      setFolders(data.folders || [])
    } catch (e) {
      setError(e.message)
      setFolders([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadFolders(currentRoot)
  }, [currentRoot, studyId])

  const handleOpen = (folder) => {
    setBreadcrumb((b) => [...b, { id: folder.id, name: folder.name }])
  }

  const handleSelect = (folder) => {
    onSelect(folder.id)
    onClose()
  }

  const goTo = (index) => {
    setBreadcrumb((b) => b.slice(0, index + 1))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="max-h-[80vh] w-full max-w-md rounded-xl border border-slate-600 bg-slate-800 p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-3 text-sm font-medium text-slate-200">Select Box folder for videos</h3>
        <div className="mb-2 flex flex-wrap gap-1 text-xs text-slate-400">
          {breadcrumb.map((item, i) => (
            <span key={item.id}>
              <button
                type="button"
                onClick={() => goTo(i)}
                className="hover:text-slate-300 hover:underline"
              >
                {item.name}
              </button>
              {i < breadcrumb.length - 1 && <span className="ml-1">›</span>}
            </span>
          ))}
        </div>
        {error && (
          <p className="mb-2 text-sm text-red-400">{error}</p>
        )}
        {loading ? (
          <p className="text-sm text-slate-500">Loading folders…</p>
        ) : (
          <ul className="max-h-64 space-y-1 overflow-y-auto">
            {folders.map((folder) => (
              <li
                key={folder.id}
                className="flex items-center justify-between gap-2 rounded border border-slate-600 bg-slate-700/50 px-2 py-1.5 text-sm text-slate-200"
              >
                <span className="min-w-0 truncate">{folder.name}</span>
                <div className="flex shrink-0 gap-1">
                  <button
                    type="button"
                    onClick={() => handleOpen(folder)}
                    className="rounded bg-slate-600 px-2 py-0.5 text-xs text-slate-300 hover:bg-slate-500"
                  >
                    Open
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSelect(folder)}
                    className="rounded bg-emerald-600 px-2 py-0.5 text-xs text-white hover:bg-emerald-500"
                  >
                    Select
                  </button>
                </div>
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
