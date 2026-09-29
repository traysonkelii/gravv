import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Input, Select } from '@/components/ui/Field'
import { toastError } from '@/components/ui/Toast'
import { useOnboardingStep, type Me } from '@/lib/api/me'
import { timeZones } from '@/utils/timezones'

const schema = z.object({
  full_name: z.string().min(1, 'Enter your name').max(120),
  role_title: z.string().max(120),
  timezone: z.string().min(1),
})
type Form = z.infer<typeof schema>

export function StepProfile({ me, onNext }: { me: Me; onNext: () => void }) {
  const save = useOnboardingStep()
  const guess = Intl.DateTimeFormat().resolvedOptions().timeZone
  const { register, handleSubmit, formState } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: {
      full_name: me.profile.full_name,
      role_title: me.profile.role_title ?? '',
      timezone: me.profile.timezone === 'UTC' && guess ? guess : me.profile.timezone,
    },
  })
  return (
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={handleSubmit(async (values) => {
        try {
          await save.mutateAsync({ step: 1, profile: values })
          onNext()
        } catch {
          toastError('Profile could not be saved', 'Check your connection and try again.')
        }
      })}
    >
      <Input
        label="Full name"
        autoComplete="name"
        {...register('full_name')}
        error={formState.errors.full_name?.message}
      />
      <Input
        label="Role"
        placeholder="Account Executive"
        hint="How you introduce yourself at work."
        {...register('role_title')}
        error={formState.errors.role_title?.message}
      />
      <Select label="Timezone" {...register('timezone')} error={formState.errors.timezone?.message}>
        {timeZones().map((tz) => (
          <option key={tz} value={tz}>
            {tz}
          </option>
        ))}
      </Select>
      <div className="mt-2 flex justify-end">
        <Button type="submit" variant="primary" loading={save.isPending}>
          Continue
        </Button>
      </div>
    </form>
  )
}
