import type { ReactNode, TdHTMLAttributes, ThHTMLAttributes } from 'react'

/* Header row steel-700, 44px rows, hairlines between rows. Scrolls horizontally on mobile; never becomes cards. */
export function Table({
  children,
  className = '',
  minWidth = 'min-w-160',
}: {
  children: ReactNode
  className?: string
  minWidth?: string
}) {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className={`w-full ${minWidth} text-sm`}>{children}</table>
    </div>
  )
}

export function THead({ children }: { children: ReactNode }) {
  return <thead className="sticky top-0 bg-steel-700 text-left text-steel-300">{children}</thead>
}

export function TH({
  children,
  numeric,
  className = '',
  ...rest
}: ThHTMLAttributes<HTMLTableCellElement> & { numeric?: boolean }) {
  return (
    <th
      scope="col"
      className={`h-11 px-3 font-medium ${numeric ? 'text-right' : ''} ${className}`}
      {...rest}
    >
      {children}
    </th>
  )
}

export function TR({
  children,
  onClick,
  className = '',
}: {
  children: ReactNode
  onClick?: () => void
  className?: string
}) {
  return (
    <tr
      onClick={onClick}
      className={`h-11 border-b border-steel-600 ${onClick ? 'cursor-pointer hover:bg-steel-700/50' : ''} ${className}`}
    >
      {children}
    </tr>
  )
}

export function TD({
  children,
  numeric,
  className = '',
  ...rest
}: TdHTMLAttributes<HTMLTableCellElement> & { numeric?: boolean }) {
  return (
    <td className={`px-3 ${numeric ? 'tnum text-right' : ''} ${className}`} {...rest}>
      {children}
    </td>
  )
}
