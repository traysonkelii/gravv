/* Onboarding progress: five 2px rectangles. Completed steel-050, current temper-500, upcoming steel-600. */
export function Progress({ steps, current }: { steps: number; current: number }) {
  return (
    <ol className="flex gap-1" aria-label={`Step ${current} of ${steps}`}>
      {Array.from({ length: steps }, (_, i) => {
        const n = i + 1
        const tone = n < current ? 'bg-steel-050' : n === current ? 'bg-temper-500' : 'bg-steel-600'
        return (
          <li
            key={n}
            aria-current={n === current ? 'step' : undefined}
            className={`h-0.5 flex-1 ${tone}`}
          />
        )
      })}
    </ol>
  )
}
