/* Number in the display face, label below, delta on the label line. No eyebrow, no animated counting. */
export function StatBlock({
  value,
  label,
  delta,
}: {
  value: string
  label: string
  delta?: { text: string; negative?: boolean }
}) {
  return (
    <div className="flex flex-col">
      <span className="tnum font-display text-3xl font-extrabold text-steel-100">{value}</span>
      <span className="text-sm text-steel-400">
        {label}
        {delta && (
          <span className={delta.negative ? 'text-rust-400' : 'text-steel-300'}> {delta.text}</span>
        )}
      </span>
    </div>
  )
}
