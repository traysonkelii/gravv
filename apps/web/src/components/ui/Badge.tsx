import type { ReactNode } from 'react'

type Tone = 'status' | 'strong' | 'steady' | 'weak' | 'drifting' | 'risk'

const tones: Record<Tone, string> = {
  status: 'border-steel-600 text-steel-300',
  strong: 'border-steel-600 text-band-strong',
  steady: 'border-steel-600 text-band-steady',
  weak: 'border-steel-600 text-band-weak',
  drifting: 'border-steel-600 text-band-drifting',
  risk: 'border-rust-400 text-rust-400',
}

export function Badge({ tone = 'status', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex h-5.5 items-center border px-2 text-xs ${tones[tone]}`}>
      {children}
    </span>
  )
}
