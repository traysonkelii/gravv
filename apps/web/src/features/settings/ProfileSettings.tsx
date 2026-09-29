import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Checkbox } from '@/components/ui/Checkbox'
import { Chip } from '@/components/ui/Chip'
import { Input, Select, Textarea } from '@/components/ui/Field'
import { toast, toastError } from '@/components/ui/Toast'
import { useMe, useUpdateMe, type Me } from '@/lib/api/me'
import { timeZones } from '@/utils/timezones'

const schema = z.object({
  full_name: z.string().min(1, 'Enter your name').max(120),
  role_title: z.string().max(120),
  timezone: z.string().min(1),
  close_deals: z.boolean(),
  expand_network: z.boolean(),
  strengthen: z.boolean(),
  track_roi: z.boolean(),
  free_text: z.string().max(500),
})
type Form = z.infer<typeof schema>
type Interest = { kind: 'professional' | 'personal'; value: string }

export function ProfileSettings() {
  const { data: me } = useMe()
  if (!me) return <p className="text-sm text-steel-400">Loading</p>
  return <ProfileForm me={me} />
}

function ProfileForm({ me }: { me: Me }) {
  const update = useUpdateMe()
  const g = me.profile.goals as Partial<Form>
  const [interests, setInterests] = useState<Interest[]>(() =>
    me.interests.map((i) => ({ kind: i.kind as Interest['kind'], value: i.value })),
  )
  const [draft, setDraft] = useState<{ kind: Interest['kind']; value: string }>({
    kind: 'professional',
    value: '',
  })
  const { register, handleSubmit, formState } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: {
      full_name: me.profile.full_name,
      role_title: me.profile.role_title ?? '',
      timezone: me.profile.timezone,
      close_deals: !!g.close_deals,
      expand_network: !!g.expand_network,
      strengthen: !!g.strengthen,
      track_roi: !!g.track_roi,
      free_text: g.free_text ?? '',
    },
  })
  return (
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={handleSubmit(async (v) => {
        try {
          await update.mutateAsync({
            full_name: v.full_name,
            role_title: v.role_title,
            timezone: v.timezone,
            goals: {
              close_deals: v.close_deals,
              expand_network: v.expand_network,
              strengthen: v.strengthen,
              track_roi: v.track_roi,
              free_text: v.free_text,
            },
            interests,
          })
          toast('Profile saved')
        } catch {
          toastError('Profile could not be saved', 'Check the fields and try again.')
        }
      })}
    >
      <Input label="Email" value={me.profile.email} disabled readOnly />
      <Input
        label="Full name"
        {...register('full_name')}
        error={formState.errors.full_name?.message}
      />
      <Input
        label="Role"
        {...register('role_title')}
        error={formState.errors.role_title?.message}
      />
      <Select label="Timezone" {...register('timezone')}>
        {timeZones().map((tz) => (
          <option key={tz} value={tz}>
            {tz}
          </option>
        ))}
      </Select>

      <h2 className="mt-4 text-md font-semibold text-steel-100">Interests</h2>
      <div className="flex flex-wrap gap-2">
        {interests.map((i) => (
          <Chip
            key={`${i.kind}:${i.value}`}
            label={`${i.value} (${i.kind})`}
            selected
            onClick={() => setInterests(interests.filter((x) => x !== i))}
          />
        ))}
        {interests.length === 0 && <p className="text-sm text-steel-400">No interests yet.</p>}
      </div>
      <div className="flex items-end gap-2">
        <Select
          label="Kind"
          value={draft.kind}
          onChange={(e) => setDraft({ ...draft, kind: e.target.value as Interest['kind'] })}
          className="w-40"
        >
          <option value="professional">Professional</option>
          <option value="personal">Personal</option>
        </Select>
        <Input
          label="Interest"
          value={draft.value}
          onChange={(e) => setDraft({ ...draft, value: e.target.value })}
          maxLength={60}
          className="flex-1"
        />
        <Button
          disabled={!draft.value.trim()}
          onClick={() => {
            setInterests([...interests, { kind: draft.kind, value: draft.value.trim() }])
            setDraft({ ...draft, value: '' })
          }}
        >
          Add
        </Button>
      </div>

      <h2 className="mt-4 text-md font-semibold text-steel-100">Goals</h2>
      <Checkbox label="Close deals" {...register('close_deals')} />
      <Checkbox label="Expand my network" {...register('expand_network')} />
      <Checkbox label="Strengthen key relationships" {...register('strengthen')} />
      <Checkbox label="Track return on relationships" {...register('track_roi')} />
      <Textarea label="Anything else" maxLength={500} {...register('free_text')} />
      <div className="flex justify-end">
        <Button type="submit" variant="primary" loading={update.isPending}>
          Save profile
        </Button>
      </div>
    </form>
  )
}
