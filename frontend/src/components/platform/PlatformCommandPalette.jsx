import { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { LayoutDashboard, KeyRound, ScrollText, Users } from 'lucide-react'

const LINKS = [
  { to: '/platform', label: 'Overview', icon: LayoutDashboard },
  { to: '/platform/users', label: 'Users', icon: Users },
  { to: '/platform/api-keys', label: 'API Keys', icon: KeyRound },
  { to: '/platform/api-logs', label: 'API Logs', icon: ScrollText },
]

/**
 * Cmd/Ctrl+K quick navigation for Platform (plan: command palette).
 */
export default function PlatformCommandPalette() {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const navigate = useNavigate()

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return LINKS
    return LINKS.filter((l) => l.label.toLowerCase().includes(s))
  }, [q])

  const go = useCallback(
    (to) => {
      navigate(to)
      setOpen(false)
      setQ('')
    },
    [navigate]
  )

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((o) => {
          if (!o) setQ('')
          return !o
        })
      }
      if (e.key === 'Escape') {
        setOpen(false)
        setQ('')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (typeof document === 'undefined' || !open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center bg-black/50 p-4 pt-[15vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Platform quick navigation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) {
          setOpen(false)
          setQ('')
        }
      }}
    >
      <div
        className="bg-popover text-popover-foreground w-full max-w-md overflow-hidden rounded-lg border border-border shadow-lg"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-3 py-2">
          <input
            autoFocus
            className="placeholder:text-muted-foreground w-full border-0 bg-transparent text-sm outline-none"
            placeholder="Go to…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Filter destinations"
          />
          <p className="text-muted-foreground mt-1 text-xs">⌘K / Ctrl+K · Esc to close</p>
        </div>
        <ul className="max-h-64 overflow-y-auto p-1">
          {filtered.map((item) => {
            const NavIcon = item.icon
            return (
              <li key={item.to}>
                <button
                  type="button"
                  className={cn(
                    'hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm',
                    'focus:bg-muted focus:outline-none'
                  )}
                  onClick={() => go(item.to)}
                >
                  <NavIcon className="text-muted-foreground size-4 shrink-0" aria-hidden />
                  {item.label}
                </button>
              </li>
            )
          })}
          {filtered.length === 0 ? (
            <li className="text-muted-foreground px-2 py-3 text-center text-sm">No matches</li>
          ) : null}
        </ul>
      </div>
    </div>,
    document.body
  )
}
