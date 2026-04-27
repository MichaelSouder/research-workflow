import { useEffect, useRef } from 'react'
import { getStageLabelForStep } from '../constants'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

const levelClass = {
  info: 'text-foreground',
  success: 'text-emerald-600 dark:text-emerald-400',
  warning: 'text-amber-600 dark:text-amber-400',
  error: 'text-destructive',
}

export default function ActivityStream({ activity }) {
  const endRef = useRef(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activity?.length])

  return (
    <section className="flex flex-col rounded-xl border border-border bg-card">
      <h2 className="border-b border-border px-3 py-2 text-sm font-medium text-foreground">
        Activity
      </h2>
      <div className="max-h-64 overflow-y-auto">
        {!activity?.length ? (
          <p className="px-3 py-4 text-sm text-muted-foreground">No activity yet.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[88px]">Time</TableHead>
                <TableHead className="w-[100px]">Stage</TableHead>
                <TableHead>Level</TableHead>
                <TableHead>Message</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activity.map((a, i) => {
                const stageLabel = getStageLabelForStep(a.step)
                return (
                  <TableRow key={i} className={levelClass[a.level] || levelClass.info}>
                    <TableCell className="whitespace-nowrap font-mono text-xs text-muted-foreground">
                      {a.timestamp ? new Date(a.timestamp).toLocaleTimeString() : '—'}
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
                    <TableCell className="text-xs capitalize">{a.level || 'info'}</TableCell>
                    <TableCell className="break-all font-mono text-xs">{a.message}</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
        <div ref={endRef} />
      </div>
    </section>
  )
}
