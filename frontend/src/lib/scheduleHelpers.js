/**
 * Helpers for the Schedule tab: parse cron, map presets to cron, human-readable description.
 * Cron format: minute hour day-of-month month day-of-week (0 = Sunday, 6 = Saturday).
 */

export const SCHEDULE_PRESETS = [
  { value: 'daily', label: 'Every day' },
  { value: 'weekdays', label: 'Weekdays (Mon–Fri)' },
  { value: 'weekly', label: 'Once a week' },
]

export const WEEKDAY_OPTIONS = [
  { value: 0, label: 'Sunday' },
  { value: 1, label: 'Monday' },
  { value: 2, label: 'Tuesday' },
  { value: 3, label: 'Wednesday' },
  { value: 4, label: 'Thursday' },
  { value: 5, label: 'Friday' },
  { value: 6, label: 'Saturday' },
]

/** Common IANA timezones for the dropdown. "Other" allows free text. */
export const COMMON_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Phoenix',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Tokyo',
  'Asia/Singapore',
  'Australia/Sydney',
]

/**
 * Parse a 5-field cron expression into preset + time/day.
 * @param {string} cron - e.g. "0 9 * * *"
 * @returns {{ preset: string, hour: number, minute: number, dayOfWeek: number | null }}
 */
export function parseCronToPreset(cron) {
  const c = (cron || '').trim()
  if (!c) return { preset: 'daily', hour: 9, minute: 0, dayOfWeek: null }

  const parts = c.split(/\s+/)
  if (parts.length !== 5) return { preset: 'custom', hour: 9, minute: 0, dayOfWeek: null }

  const [minStr, hourStr, , , dowStr] = parts
  const minute = parseInt(minStr, 10)
  const hour = parseInt(hourStr, 10)
  if (Number.isNaN(minute) || Number.isNaN(hour)) return { preset: 'custom', hour: 9, minute: 0, dayOfWeek: null }

  // Daily: 0 mm hh * * *
  if (parts[2] === '*' && parts[3] === '*' && parts[4] === '*') {
    return { preset: 'daily', hour, minute, dayOfWeek: null }
  }
  // Weekdays: 0 mm hh * * 1-5
  if (parts[2] === '*' && parts[3] === '*' && parts[4] === '1-5') {
    return { preset: 'weekdays', hour, minute, dayOfWeek: null }
  }
  // Weekly: 0 mm hh * * d
  const dowMatch = parts[4].match(/^([0-6])$/)
  if (parts[2] === '*' && parts[3] === '*' && dowMatch) {
    return { preset: 'weekly', hour, minute, dayOfWeek: parseInt(dowMatch[1], 10) }
  }

  return { preset: 'custom', hour: 9, minute: 0, dayOfWeek: null }
}

/**
 * Build cron expression from preset and time/day.
 * Cron format: minute hour day-of-month month day-of-week (5 fields).
 * @param {string} preset - 'daily' | 'weekdays' | 'weekly' | 'custom'
 * @param {number} hour - 0-23
 * @param {number} minute - 0-59
 * @param {number | null} dayOfWeek - 0-6 for weekly, null otherwise
 * @param {string} customCron - used when preset === 'custom'
 */
export function presetToCron(preset, hour, minute, dayOfWeek, customCron = '') {
  if (preset === 'custom' && customCron.trim()) return customCron.trim()
  const m = Math.min(59, Math.max(0, minute))
  const h = Math.min(23, Math.max(0, hour))
  if (preset === 'daily') return `${m} ${h} * * *`
  if (preset === 'weekdays') return `${m} ${h} * * 1-5`
  if (preset === 'weekly' && dayOfWeek != null) return `${m} ${h} * * ${dayOfWeek}`
  return `${m} ${h} * * *`
}

/**
 * Human-readable description of the schedule (no timezone in string; tz is for context).
 * @param {string} cron
 * @param {string} timezone - e.g. America/Chicago
 */
export function describeSchedule(cron, timezone = '') {
  const c = (cron || '').trim()
  if (!c) return 'No schedule set'
  const { preset, hour, minute, dayOfWeek } = parseCronToPreset(c)
  const timeStr = formatTime(hour, minute)
  if (preset === 'custom') {
    return timezone ? `At ${timeStr} (${timezone})` : `At ${timeStr}`
  }
  let when = ''
  if (preset === 'daily') when = `Every day at ${timeStr}`
  else if (preset === 'weekdays') when = `Weekdays at ${timeStr}`
  else if (preset === 'weekly' && dayOfWeek != null) {
    const dayLabel = WEEKDAY_OPTIONS.find((d) => d.value === dayOfWeek)?.label ?? `Day ${dayOfWeek}`
    when = `${dayLabel}s at ${timeStr}`
  } else when = `At ${timeStr}`
  return timezone ? `${when} (${timezone})` : when
}

function formatTime(hour, minute) {
  const h = hour % 12 || 12
  const m = String(minute).padStart(2, '0')
  const ampm = hour < 12 ? 'AM' : 'PM'
  return `${h}:${m} ${ampm}`
}
