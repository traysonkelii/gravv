import type { ReactNode } from 'react'

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string
  body: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-start gap-3 py-12">
      <h2 className="text-md font-semibold text-steel-100">{title}</h2>
      <p className="max-w-prose text-base text-steel-300">{body}</p>
      {action}
    </div>
  )
}
