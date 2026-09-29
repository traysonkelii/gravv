import type { ButtonHTMLAttributes } from 'react'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean; label: string }

export function Chip({ selected = false, label, className = '', ...rest }: Props) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={`inline-flex h-9 items-center border px-3 text-sm transition-colors duration-(--duration-fast) ${
        selected
          ? 'border-temper-500 text-steel-100'
          : 'border-steel-600 text-steel-300 hover:text-steel-100'
      } ${className}`}
      {...rest}
    >
      {label}
    </button>
  )
}
