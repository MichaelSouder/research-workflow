import * as React from 'react'
import { format } from 'date-fns'
import { CalendarIcon } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const HOURS = Array.from({ length: 24 }, (_, i) => i)
const MINUTES = Array.from({ length: 60 }, (_, i) => i)

function pad2(n) {
  return String(n).padStart(2, '0')
}

/** @param {Date} date */
export function composeLocalDateTimeString(date, hour, minute) {
  const x = new Date(date)
  x.setHours(hour, minute, 0, 0)
  return `${x.getFullYear()}-${pad2(x.getMonth() + 1)}-${pad2(x.getDate())}T${pad2(hour)}:${pad2(minute)}`
}

/** @param {string | undefined} v */
export function parseLocalDateTimeParts(v) {
  if (!v || !String(v).trim()) return null
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return null
  return {
    instant: d,
    day: new Date(d.getFullYear(), d.getMonth(), d.getDate()),
    hour: d.getHours(),
    minute: d.getMinutes(),
  }
}

/**
 * Controlled datetime for API key expiry: value is `YYYY-MM-DDTHH:mm` in local time (same as former datetime-local).
 */
export function DateTimePicker({
  id,
  value,
  onChange,
  disabled = false,
  placeholder = 'Pick date and time',
  allowClear = false,
  className,
}) {
  const [open, setOpen] = React.useState(false)
  const parsed = React.useMemo(() => parseLocalDateTimeParts(value), [value])

  const display = parsed
    ? format(parsed.instant, 'PPp')
    : null

  const setFromParts = (day, hour, minute) => {
    if (!day) {
      onChange('')
      return
    }
    onChange(composeLocalDateTimeString(day, hour, minute))
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          disabled={disabled}
          className={cn(
            'w-full justify-start text-left font-normal',
            !display && 'text-muted-foreground',
            className
          )}
        >
          <CalendarIcon className="mr-2 size-4 shrink-0 opacity-70" aria-hidden />
          {display ?? placeholder}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <div className="flex flex-col gap-3 p-3">
          <Calendar
            mode="single"
            required={false}
            selected={parsed?.day}
            onSelect={(d) => {
              if (!d) {
                if (allowClear) onChange('')
                return
              }
              const h = parsed?.hour ?? 12
              const m = parsed?.minute ?? 0
              setFromParts(d, h, m)
            }}
          />
          <div className="flex flex-wrap items-end gap-3 border-t border-border px-1 pb-1 pt-2">
            <div className="grid gap-1.5">
              <Label htmlFor={id ? `${id}-hour` : undefined} className="text-xs text-muted-foreground">
                Hour
              </Label>
              <Select
                value={String(parsed?.hour ?? 12)}
                onValueChange={(v) => {
                  const hour = Number(v)
                  const day = parsed?.day ?? new Date()
                  const m = parsed?.minute ?? 0
                  setFromParts(day, hour, m)
                }}
                disabled={disabled}
              >
                <SelectTrigger id={id ? `${id}-hour` : undefined} className="h-9 w-[88px]">
                  <SelectValue placeholder="Hr" />
                </SelectTrigger>
                <SelectContent position="popper" className="z-[100] max-h-60">
                  {HOURS.map((h) => (
                    <SelectItem key={h} value={String(h)}>
                      {pad2(h)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor={id ? `${id}-minute` : undefined} className="text-xs text-muted-foreground">
                Minute
              </Label>
              <Select
                value={String(parsed?.minute ?? 0)}
                onValueChange={(v) => {
                  const minute = Number(v)
                  const day = parsed?.day ?? new Date()
                  const h = parsed?.hour ?? 12
                  setFromParts(day, h, minute)
                }}
                disabled={disabled}
              >
                <SelectTrigger id={id ? `${id}-minute` : undefined} className="h-9 w-[88px]">
                  <SelectValue placeholder="Min" />
                </SelectTrigger>
                <SelectContent position="popper" className="z-[100] max-h-60">
                  {MINUTES.map((m) => (
                    <SelectItem key={m} value={String(m)}>
                      {pad2(m)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {allowClear ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="mb-0.5 ml-auto"
                onClick={() => {
                  onChange('')
                  setOpen(false)
                }}
              >
                Clear
              </Button>
            ) : null}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
