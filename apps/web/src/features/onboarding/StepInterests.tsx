import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { Chip } from '@/components/ui/Chip'
import { Input } from '@/components/ui/Field'
import { toastError } from '@/components/ui/Toast'
import { useOnboardingStep, type Me } from '@/lib/api/me'

const suggestions = {
  professional: [
    'Government contracting',
    'Program management',
    'Enterprise sales',
    'Aerospace',
    'Defense',
    'Policy',
    'Consulting',
    'Fundraising',
  ],
  personal: [
    'Golf',
    'Trail running',
    'Barbecue',
    'Pinball',
    'Sailing',
    'Cycling',
    'Cooking',
    'Astronomy',
    'Travel',
  ],
} as const

type Kind = keyof typeof suggestions
type Interest = { kind: Kind; value: string }

function Picker({
  kind,
  title,
  value,
  onChange,
}: {
  kind: Kind
  title: string
  value: Interest[]
  onChange: (v: Interest[]) => void
}) {
  const [custom, setCustom] = useState('')
  const mine = value.filter((i) => i.kind === kind)
  const has = (v: string) => mine.some((i) => i.value.toLowerCase() === v.toLowerCase())
  const toggle = (v: string) =>
    onChange(
      has(v)
        ? value.filter((i) => !(i.kind === kind && i.value.toLowerCase() === v.toLowerCase()))
        : [...value, { kind, value: v }],
    )
  const add = (e: FormEvent) => {
    e.preventDefault()
    const v = custom.trim()
    if (v && !has(v)) onChange([...value, { kind, value: v }])
    setCustom('')
  }
  const extra = mine.filter(
    (i) =>
      !(suggestions[kind] as readonly string[]).some(
        (s) => s.toLowerCase() === i.value.toLowerCase(),
      ),
  )
  return (
    <section>
      <h2 className="text-md font-semibold text-steel-100">{title}</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {suggestions[kind].map((s) => (
          <Chip key={s} label={s} selected={has(s)} onClick={() => toggle(s)} />
        ))}
        {extra.map((i) => (
          <Chip key={i.value} label={i.value} selected onClick={() => toggle(i.value)} />
        ))}
      </div>
      <form onSubmit={add} className="mt-3 flex items-end gap-2">
        <Input
          label="Add your own"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          maxLength={60}
          className="flex-1"
        />
        <Button type="submit" disabled={!custom.trim()}>
          Add
        </Button>
      </form>
    </section>
  )
}

export function StepInterests({
  me,
  onNext,
  onBack,
}: {
  me: Me
  onNext: () => void
  onBack: () => void
}) {
  const save = useOnboardingStep()
  const [value, setValue] = useState<Interest[]>(
    me.interests.map((i) => ({ kind: i.kind as Kind, value: i.value })),
  )
  return (
    <div className="flex flex-col gap-8">
      <p className="text-base text-steel-300">
        Gravv points out common ground when a contact shares one of these.
      </p>
      <Picker kind="professional" title="Professional" value={value} onChange={setValue} />
      <Picker kind="personal" title="Personal" value={value} onChange={setValue} />
      <div className="flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
        <Button
          variant="primary"
          loading={save.isPending}
          onClick={async () => {
            try {
              await save.mutateAsync({ step: 2, interests: value })
              onNext()
            } catch {
              toastError('Interests could not be saved', 'Check your connection and try again.')
            }
          }}
        >
          Continue
        </Button>
      </div>
    </div>
  )
}
