/**
 * Palette of pipeline node types by category. Add a node by clicking a type (editable mode only).
 */
import { NODE_CATEGORIES, NODE_CONFIG } from './componentConfig'
import { Button } from '@/components/ui/button'

export default function PipelineNodePalette({ onAddNode, editable }) {
  if (!editable) return null
  return (
    <div className="rounded-lg border border-border bg-muted/30 p-3" aria-label="Add pipeline nodes">
      <p className="mb-2 text-xs font-medium text-muted-foreground">Add node</p>
      <div className="space-y-3">
        {NODE_CATEGORIES.map((cat) => (
          <div key={cat.id}>
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              {cat.label}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {cat.nodeTypes.map((nodeType) => {
                const config = NODE_CONFIG[nodeType]
                const label = config?.label ?? nodeType.replace(/_/g, ' ')
                return (
                  <Button
                    key={nodeType}
                    type="button"
                    variant="outline"
                    size="sm"
                    className="text-xs"
                    onClick={() => onAddNode(nodeType)}
                    aria-label={`Add ${label} node`}
                  >
                    + {label}
                  </Button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
