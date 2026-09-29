import { initials } from '@/lib/format'
import type { Band } from '@/lib/copy'

const sizes = { 32: 'size-8 text-sm', 40: 'size-10 text-base', 64: 'size-16 text-xl' } as const

/* Square, initials in the display face; the fill is the brushed steel tinted by band. */
export function Avatar({
  name,
  band = 'weak',
  size = 40,
}: {
  name: string
  band?: Band
  size?: 32 | 40 | 64
}) {
  return (
    <span
      aria-hidden
      className={`brushed inline-flex shrink-0 items-center justify-center border border-steel-500 bg-steel-700 font-display font-bold text-steel-100 ${sizes[size]}`}
      style={{
        backgroundColor: `color-mix(in srgb, var(--color-band-${band}) 35%, var(--color-steel-700))`,
      }}
    >
      {initials(name)}
    </span>
  )
}
