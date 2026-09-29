import type { LucideIcon, LucideProps } from 'lucide-react'

type Props = Omit<LucideProps, 'ref'> & { icon: LucideIcon; label?: string }

/* Every icon in the product goes through here: angular strokes to match the edges, no other icon source. */
export function Icon({ icon: Glyph, label, size = 20, ...rest }: Props) {
  return (
    <Glyph
      size={size}
      strokeWidth={1.75}
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden={label ? undefined : true}
      aria-label={label}
      role={label ? 'img' : undefined}
      {...rest}
    />
  )
}
