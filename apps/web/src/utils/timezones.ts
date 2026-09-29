const fallback = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Berlin',
  'Asia/Tokyo',
  'Australia/Sydney',
]

export function timeZones(): string[] {
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] }
  try {
    const list = intl.supportedValuesOf?.('timeZone')
    if (list && list.length) return list.includes('UTC') ? list : ['UTC', ...list]
  } catch {
    /* older engines */
  }
  return fallback
}
