import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { cn } from '@/lib/utils'

const stateStyles = {
  pending: 'border-muted bg-muted/30 text-muted-foreground',
  in_progress: 'border-primary bg-primary/10 text-primary',
  done: 'border-emerald-600/50 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  error: 'border-destructive bg-destructive/10 text-destructive',
}

const stateLabels = {
  pending: 'Pending',
  in_progress: 'In progress',
  done: 'Done',
  error: 'Error',
}

function PipelineFlowNode({ data }) {
  const { label, state = 'pending', selected } = data
  const ariaLabel = [label, stateLabels[state], selected ? 'Selected' : null].filter(Boolean).join(', ')

  return (
    <div
      className={cn(
        'rounded-lg border px-4 py-3 shadow-sm min-w-[140px] text-center transition-colors cursor-pointer',
        stateStyles[state] ?? stateStyles.pending,
        state === 'in_progress' && 'animate-pulse',
        selected && 'ring-2 ring-primary ring-offset-2 ring-offset-background'
      )}
      role="img"
      aria-label={ariaLabel}
    >
      <Handle type="target" position={Position.Left} className="!size-2.5 !border !border-border !bg-background" />
      <div className="font-medium">{label}</div>
      <div className="mt-1 text-xs opacity-80">{stateLabels[state]}</div>
      <Handle type="source" position={Position.Right} className="!size-2.5 !border !border-border !bg-background" />
    </div>
  )
}

export default memo(PipelineFlowNode)
