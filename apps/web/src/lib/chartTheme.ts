/* Shared Recharts theme (Section 10.5). Colors are read from the tokens at call time so themes stay in sync. */
export function token(name: string): string {
  if (typeof window === 'undefined') return ''
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

export const bandColor = (band: string) => `var(--color-band-${band})`

export const kindShade: Record<string, string> = {
  meeting: 'var(--color-steel-050)',
  call: 'var(--color-steel-200)',
  email: 'var(--color-steel-300)',
  message: 'var(--color-steel-400)',
  note: 'var(--color-steel-500)',
  event: 'var(--color-steel-300)',
  introduction: 'var(--color-steel-200)',
  gift: 'var(--color-temper-300)',
  other: 'var(--color-oxide-500)',
}

export const chart = {
  grid: { stroke: 'var(--color-steel-700)', strokeWidth: 1 },
  axis: {
    stroke: 'var(--color-steel-600)',
    tick: { fill: 'var(--color-steel-400)', fontSize: 12 },
  },
  tooltip: {
    contentStyle: {
      background: 'var(--color-steel-800)',
      border: '1px solid var(--color-steel-600)',
      borderRadius: 0,
      color: 'var(--color-steel-200)',
      fontSize: 13,
    },
    itemStyle: { color: 'var(--color-steel-200)' },
    labelStyle: { color: 'var(--color-steel-400)' },
    cursor: { fill: 'var(--color-steel-700)', opacity: 0.5 },
  },
}
