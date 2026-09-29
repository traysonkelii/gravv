/* 32 vertical bars, 3px wide. steel-300 idle, rust-400 while recording. */
export function LevelMeter({ levels, recording }: { levels: number[]; recording: boolean }) {
  return (
    <div aria-hidden className="flex h-12 items-end gap-0.5">
      {levels.map((v, i) => (
        <span
          key={i}
          className={`w-0.75 ${recording ? 'bg-rust-400' : 'bg-steel-300'}`}
          style={{ height: `${Math.max(4, Math.round(v * 48))}px` }}
        />
      ))}
    </div>
  )
}
