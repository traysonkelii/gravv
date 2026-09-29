import { useForm } from 'react-hook-form'
import { Button } from '@/components/ui/Button'
import { Checkbox } from '@/components/ui/Checkbox'
import { Textarea } from '@/components/ui/Field'
import { toastError } from '@/components/ui/Toast'
import { useOnboardingStep, type Me } from '@/lib/api/me'

type Form = {
  close_deals: boolean
  expand_network: boolean
  strengthen: boolean
  track_roi: boolean
  free_text: string
}

export function StepGoals({
  me,
  onNext,
  onBack,
}: {
  me: Me
  onNext: () => void
  onBack: () => void
}) {
  const save = useOnboardingStep()
  const g = me.profile.goals as Partial<Form>
  const { register, handleSubmit } = useForm<Form>({
    defaultValues: {
      close_deals: !!g.close_deals,
      expand_network: !!g.expand_network,
      strengthen: !!g.strengthen,
      track_roi: !!g.track_roi,
      free_text: g.free_text ?? '',
    },
  })
  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={handleSubmit(async (values) => {
        try {
          await save.mutateAsync({ step: 3, goals: values })
          onNext()
        } catch {
          toastError('Goals could not be saved', 'Check your connection and try again.')
        }
      })}
    >
      <Checkbox
        label="Close deals"
        description="Keep decision makers warm through long cycles."
        {...register('close_deals')}
      />
      <Checkbox
        label="Expand my network"
        description="Find introductions through people I already know."
        {...register('expand_network')}
      />
      <Checkbox
        label="Strengthen key relationships"
        description="Never let an important contact drift."
        {...register('strengthen')}
      />
      <Checkbox
        label="Track return on relationships"
        description="See which relationships move pipeline."
        {...register('track_roi')}
      />
      <Textarea
        label="Anything else"
        hint="Optional. One or two sentences."
        maxLength={500}
        className="mt-4"
        {...register('free_text')}
      />
      <div className="mt-4 flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
        <Button type="submit" variant="primary" loading={save.isPending}>
          Continue
        </Button>
      </div>
    </form>
  )
}
