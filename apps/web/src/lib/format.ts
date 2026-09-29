const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/* "3h ago", "2 weeks ago", "in 2 days", "overdue 9 days" */
export function relativeTime(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return 'never'
  const diff = now.getTime() - new Date(iso).getTime()
  const abs = Math.abs(diff)
  const past = diff >= 0
  let text: string
  if (abs < MINUTE) text = 'just now'
  else if (abs < HOUR) text = `${Math.floor(abs / MINUTE)}m`
  else if (abs < DAY) text = `${Math.floor(abs / HOUR)}h`
  else if (abs < 14 * DAY) text = `${Math.floor(abs / DAY)}d`
  else if (abs < 60 * DAY) text = `${Math.floor(abs / (7 * DAY))} weeks`
  else if (abs < 365 * DAY) text = `${Math.floor(abs / (30 * DAY))} months`
  else text = `${Math.floor(abs / (365 * DAY))} years`
  if (text === 'just now') return text
  return past ? `${text} ago` : `in ${text}`
}

export function overdueLabel(
  iso: string | null | undefined,
  now: Date = new Date(),
): string | null {
  if (!iso) return null
  const days = Math.floor((now.getTime() - new Date(iso).getTime()) / DAY)
  if (days < 1) return null
  return `overdue ${days} day${days === 1 ? '' : 's'}`
}

export function dueLabel(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return 'no date'
  const overdue = overdueLabel(iso, now)
  if (overdue) return overdue
  const days = Math.floor((new Date(iso).getTime() - now.getTime()) / DAY)
  if (days <= 0) return 'due today'
  if (days === 1) return 'due tomorrow'
  return `due in ${days} days`
}

/* 250000000 cents -> "$2.5M"; 820000 -> "$8.2K"; 0 -> "$0" */
export function compactCurrency(cents: number, currency = 'USD'): string {
  const value = cents / 100
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    notation: 'compact',
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  }).format(value)
}

export function formatDate(iso: string | null | undefined, timeZone?: string): string {
  if (!iso) return ''
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone,
  }).format(new Date(iso))
}

export function formatDateTime(iso: string | null | undefined, timeZone?: string): string {
  if (!iso) return ''
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone,
  }).format(new Date(iso))
}

export function initials(name: string): string {
  const parts = name
    .replace(/^(Col|Dr|Gen|Mr|Ms|Mrs|Maj|Capt|Lt)\.?\s+/i, '')
    .split(/\s+/)
    .filter(Boolean)
  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : ''
  return (first + last).toUpperCase() || '?'
}

export function signedDelta(n: number | null | undefined, suffix = ''): string {
  if (n === null || n === undefined) return ''
  return `${n > 0 ? '+' : ''}${n}${suffix}`
}
