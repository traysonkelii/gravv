import { useEffect, useRef, useState } from 'react'
import type { Band } from '@/lib/copy'
import { copy } from '@/lib/copy'

type Props = {
  score: number
  band: Band
  animate?: boolean
  showLabel?: boolean
  className?: string
}

/* 6px bar, chamfered right end, band-colored fill. When `animate` is set the fill starts at zero on mount and
   transitions to the score once (the contact page). Reduced motion shows the final state immediately. */
export function ScoreBlade({
  score,
  band,
  animate = false,
  showLabel = true,
  className = '',
}: Props) {
  const reduced =
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const [mounted, setMounted] = useState(!animate || reduced)
  const frame = useRef<number | null>(null)
  useEffect(() => {
    if (mounted) return
    frame.current = requestAnimationFrame(() => setMounted(true))
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current)
    }
  }, [mounted])
  const width = mounted ? score : 0
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <div
        className="h-1.5 flex-1 bg-steel-700"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score}
        aria-label={`${copy.gravity} ${score}, ${copy.band[band]}`}
      >
        <div
          className="chamfer-tr h-full"
          style={{
            width: `${width}%`,
            backgroundColor: `var(--color-band-${band})`,
            transition: 'width var(--duration-blade) var(--ease-machined)',
          }}
        />
      </div>
      {showLabel && (
        <span className="tnum shrink-0 text-sm text-steel-100">
          {score} <span className="text-steel-400">{copy.band[band]}</span>
        </span>
      )}
    </div>
  )
}
