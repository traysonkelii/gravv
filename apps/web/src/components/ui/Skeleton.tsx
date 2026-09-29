/* steel-700 rectangles matching the content shape. No shimmer. */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`bg-steel-700 ${className}`} />
}

export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-busy>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-14 w-full" />
      ))}
    </div>
  )
}
