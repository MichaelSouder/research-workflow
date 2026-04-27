import { getStageLabelForStep } from '../constants'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export default function ErrorLog({ errors }) {
  return (
    <section className="flex flex-col rounded-xl border border-border bg-card">
      <h2 className="border-b border-border px-3 py-2 text-sm font-medium text-foreground">
        Errors
      </h2>
      <div className="max-h-64 overflow-y-auto">
        {!errors?.length ? (
          <p className="px-3 py-4 text-sm text-muted-foreground">No errors.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[88px]">Time</TableHead>
                <TableHead className="w-[100px]">Stage</TableHead>
                <TableHead className="w-[80px]">Level</TableHead>
                <TableHead>Message</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {errors.map((e, i) => {
                const stageLabel = getStageLabelForStep(e.step)
                const rowClass = e.level === 'error' ? 'text-destructive' : 'text-amber-600 dark:text-amber-400'
                return (
                  <TableRow key={i} className={rowClass}>
                    <TableCell className="whitespace-nowrap font-mono text-xs text-muted-foreground">
                      {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '—'}
                    </TableCell>
                    <TableCell className="text-xs">
                      {stageLabel ? (
                        <span className="rounded-md bg-muted px-1.5 py-0.5 font-medium text-muted-foreground">
                          {stageLabel}
                        </span>
                      ) : (
                        '—'
                      )}
                    </TableCell>
                    <TableCell className="text-xs capitalize">{e.level || 'error'}</TableCell>
                    <TableCell className="break-all font-mono text-xs">{e.message}</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </section>
  )
}
