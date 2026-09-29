import type { HTMLAttributes, ReactNode } from 'react'

type Props = HTMLAttributes<HTMLDivElement> & {
  raised?: boolean
  children: ReactNode
  as?: 'div' | 'section'
}

export function Plate({ raised, className = '', children, as: Tag = 'div', ...rest }: Props) {
  return (
    <Tag
      className={`${raised ? 'bg-steel-700 shadow-plate-raised' : 'bg-steel-800 shadow-plate'} border border-steel-600 p-4 md:p-6 ${className}`}
      {...rest}
    >
      {children}
    </Tag>
  )
}
