import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getPlatformSummary } from '../api'
import AdminSection from '../components/platform/AdminSection'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { KeyRound, ScrollText, Users } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

function StatCard({ title, value, hint, icon: Icon, to }) {
  const inner = (
    <Card className="overflow-hidden border-border shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        {Icon ? <Icon className="size-4 text-muted-foreground" aria-hidden /> : null}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold tabular-nums">{value}</div>
        {hint ? <CardDescription className="mt-1">{hint}</CardDescription> : null}
      </CardContent>
    </Card>
  )
  if (to) {
    return (
      <Link to={to} className="block transition-opacity hover:opacity-90">
        {inner}
      </Link>
    )
  }
  return inner
}

export default function PlatformDashboardPage() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const data = await getPlatformSummary()
        if (!cancelled) setStats(data)
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-full max-w-lg" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return <p className="text-destructive">{error}</p>
  }

  return (
    <div className="space-y-6">
      <AdminSection
        title="Overview"
        description="Quick counts for users, API keys, and tool invocations (last 24 hours and 7 days)."
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Users"
          value={stats?.userCount ?? '—'}
          hint="Registered accounts"
          icon={Users}
          to="/platform/users"
        />
        <StatCard
          title="Active API Keys"
          value={stats?.mcpKeyActiveCount ?? '—'}
          hint="Non-revoked MCP keys"
          icon={KeyRound}
          to="/platform/api-keys"
        />
        <StatCard
          title="Tool Calls (24h)"
          value={stats?.invocations24h ?? '—'}
          hint={`${stats?.failedInvocations24h ?? 0} failed`}
          icon={ScrollText}
          to="/platform/api-logs"
        />
        <StatCard
          title="Tool Calls (7d)"
          value={stats?.invocations7d ?? '—'}
          hint="All statuses"
          icon={ScrollText}
          to="/platform/api-logs"
        />
      </div>
    </div>
  )
}
