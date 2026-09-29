import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  loading?: boolean
  loadingLabel?: string
  children: ReactNode
}

const base =
  'relative inline-flex h-11 md:h-10 items-center justify-center gap-2 px-4 text-sm font-medium select-none ' +
  'transition-colors duration-(--duration-fast) ease-(--ease-machined) disabled:cursor-not-allowed disabled:opacity-60'

const variants: Record<Variant, string> = {
  primary: 'bg-temper-500 text-steel-950 chamfer-br active:bg-temper-600 active:shadow-pressed',
  secondary: 'bg-steel-700 text-steel-100 shadow-plate hover:bg-steel-600 active:shadow-pressed',
  ghost: 'bg-transparent text-steel-300 hover:bg-steel-700 hover:text-steel-100',
  danger: 'bg-rust-500 text-steel-050 active:bg-rust-700 active:shadow-pressed',
}

export function Button({
  variant = 'secondary',
  loading = false,
  loadingLabel = 'Saving...',
  className = '',
  children,
  disabled,
  type = 'button',
  ...rest
}: Props) {
  return (
    <button
      type={type}
      className={`${base} ${variants[variant]} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {variant === 'primary' && (
        <span aria-hidden className="edge-highlight pointer-events-none absolute inset-x-0 top-0" />
      )}
      {loading ? loadingLabel : children}
    </button>
  )
}

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string
  children: ReactNode
  active?: boolean
}

export function IconButton({ label, children, className = '', active, ...rest }: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex size-11 md:size-10 items-center justify-center transition-colors duration-(--duration-fast) hover:bg-steel-700 ${active ? 'text-temper-500' : 'text-steel-300'} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}
