import { Link, Outlet, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useAuth } from '../contexts/AuthContext'
import Breadcrumb from './Breadcrumb'
import PlatformCommandPalette from './platform/PlatformCommandPalette'

const NAV = [
  { to: '/platform', label: 'Overview', end: true },
  { to: '/platform/users', label: 'Users' },
  { to: '/platform/api-keys', label: 'API Keys' },
  { to: '/platform/api-logs', label: 'API Logs' },
]

export default function PlatformLayout() {
  const { isSuperuser } = useAuth()
  const location = useLocation()
  const path = location.pathname

  if (!isSuperuser) {
    return (
      <div className="min-h-full bg-muted/30 p-4 md:p-6">
        <main className="mx-auto max-w-6xl">
          <p className="text-muted-foreground">You don&apos;t have access to platform administration.</p>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-full bg-muted/30 text-foreground">
      <main className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
        <Breadcrumb
          items={[{ label: 'Home', to: '/' }, { label: 'Platform' }]}
          className="mb-2"
        />
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Platform</h1>
          <p className="text-sm text-muted-foreground">
            Superuser tools: users, MCP and tool API keys, and request audit logs. Press{' '}
            <kbd className="bg-muted rounded border border-border px-1.5 py-0.5 font-mono text-xs">⌘K</kbd> /{' '}
            <kbd className="bg-muted rounded border border-border px-1.5 py-0.5 font-mono text-xs">Ctrl+K</kbd> for quick
            navigation.
          </p>
        </div>
        <PlatformCommandPalette />
        <nav
          className="flex flex-wrap gap-2 border-b border-border pb-3"
          aria-label="Platform sections"
        >
          {NAV.map(({ to, label, end }) => {
            const active = end ? path === to || path === `${to}/` : path === to || path.startsWith(`${to}/`)
            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  'rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  active
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                {label}
              </Link>
            )
          })}
        </nav>
        <Outlet />
      </main>
    </div>
  )
}
