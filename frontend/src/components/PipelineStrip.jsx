import { STAGE_ORDER, STAGE_LABELS, STEP_TO_STAGE, getStageState } from '../constants'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const stageStateStyles = {
  pending: 'border-muted bg-muted/30 text-muted-foreground',
  in_progress: 'border-primary bg-primary/10 text-primary',
  done: 'border-emerald-600/50 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  error: 'border-destructive bg-destructive/10 text-destructive',
}

export default function PipelineStrip({ status, currentStep }) {
  const currentStageId = status === 'completed' ? null : (STEP_TO_STAGE[currentStep] ?? null)
  const currentStageIndex = currentStageId ? STAGE_ORDER.indexOf(currentStageId) : -1

  return (
    <section
      className="rounded-xl border border-border bg-card p-4"
      aria-label="Pipeline stages"
    >
      <h2 className="mb-3 text-sm font-medium text-foreground">Pipeline</h2>
      <div className="flex flex-wrap items-center justify-between gap-4 sm:justify-start">
        {STAGE_ORDER.map((stageId, i) => {
          const state = getStageState(stageId, i, currentStageIndex, status || 'idle')
          const isLast = i === STAGE_ORDER.length - 1
          return (
            <div key={stageId} className="flex items-center gap-2">
              <Badge
                variant="outline"
                className={cn(
                  'font-medium transition-colors',
                  stageStateStyles[state],
                  state === 'in_progress' && 'animate-pulse'
                )}
              >
                <span
                  className={cn(
                    'mr-1.5 size-2 rounded-full',
                    state === 'pending' && 'bg-muted-foreground/50',
                    state === 'in_progress' && 'bg-primary',
                    state === 'done' && 'bg-emerald-500',
                    state === 'error' && 'bg-destructive'
                  )}
                />
                {STAGE_LABELS[stageId]}
              </Badge>
              {!isLast && (
                <span className="text-muted-foreground/60 px-1" aria-hidden="true">
                  →
                </span>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
