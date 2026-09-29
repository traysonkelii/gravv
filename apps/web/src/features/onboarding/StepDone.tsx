import { Button } from '@/components/ui/Button'
import { toastError } from '@/components/ui/Toast'
import { useOnboardingStep } from '@/lib/api/me'

const next = [
  'Add a contact or capture a note about someone you met.',
  'Add your AI provider key under Settings, AI so Gravv can extract facts and follow-ups from each note for you to confirm.',
  'Each relationship gets a Gravity score that reflects how current it is.',
  'Insights flag who needs attention and where a warm introduction exists.',
]

export function StepDone({ onDone }: { onDone: () => void }) {
  const save = useOnboardingStep()
  return (
    <div className="flex flex-col gap-6">
      <p className="text-base text-steel-300">
        Your workspace is ready. Here is what happens next.
      </p>
      <ul className="flex flex-col gap-2 text-base text-steel-200">
        {next.map((line) => (
          <li key={line} className="border-l-2 border-steel-600 pl-3">
            {line}
          </li>
        ))}
      </ul>
      <div className="flex justify-end">
        <Button
          variant="primary"
          loading={save.isPending}
          loadingLabel="Opening..."
          onClick={async () => {
            try {
              await save.mutateAsync({ step: 5 })
              onDone()
            } catch {
              toastError('Could not finish onboarding', 'Check your connection and try again.')
            }
          }}
        >
          Open Gravv
        </Button>
      </div>
    </div>
  )
}
