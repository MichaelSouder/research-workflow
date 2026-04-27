import { STATUS_LABELS } from '../constants'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const STATUS_VARIANTS = {
  idle: 'secondary',
  running: 'default',
  completed: 'default',
  failed: 'destructive',
  stopped: 'secondary',
}

/**
 * Study run toolbar — status + Start/Stop only.
 * Profile and app nav live in AppTopBar / AppSidebar (avoid a second top bar under AppLayout).
 */
export default function Header({
  status,
  onStart,
  onStop,
  starting,
  stopping,
  configOverrides,
  canEdit = true,
  /** When false, only pipeline status is shown (e.g. Distribution). Hide Start/Stop on non-run pages. */
  showRunControls = true,
}) {
  const running = status === 'running'
  const statusVariant = STATUS_VARIANTS[status] || 'secondary'
  const showStatusStrip = Boolean(status && status !== 'idle')
  const showActions = canEdit && showRunControls

  if (!showStatusStrip && !showActions) {
    return null
  }

  return (
    <header
      className={cn(
        'sticky top-0 z-30 flex flex-wrap items-center justify-end gap-2 border-b border-border bg-card/95 px-4 py-2 backdrop-blur supports-[backdrop-filter]:bg-card/80 md:gap-3 md:px-6'
      )}
    >
      {showStatusStrip ? (
        <Badge variant={statusVariant} className={cn(status === 'running' && 'animate-pulse')}>
          <span className="mr-1.5 size-2 rounded-full bg-current opacity-80" />
          {STATUS_LABELS[status] || status}
        </Badge>
      ) : null}
      {showActions ? (
        <>
          <Button onClick={() => onStart(configOverrides)} disabled={running || starting} size="sm">
            {starting ? 'Starting…' : 'Start'}
          </Button>
          <Button variant="destructive" onClick={onStop} disabled={!running || stopping} size="sm">
            {stopping ? 'Stopping…' : 'Stop'}
          </Button>
        </>
      ) : null}
    </header>
  )
}
