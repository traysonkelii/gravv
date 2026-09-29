import { Button } from '@/components/ui/Button'
import { Plate } from '@/components/ui/Plate'
import { toastError } from '@/components/ui/Toast'
import { useOnboardingStep } from '@/lib/api/me'

export const integrationPlates = [
  { key: 'google', name: 'Google', detail: 'Gmail and Google Calendar', soon: true },
  { key: 'microsoft', name: 'Microsoft', detail: 'Outlook and Microsoft 365 Calendar', soon: true },
  { key: 'salesforce', name: 'Salesforce', detail: 'Sync notes and opportunities', soon: true },
  { key: 'hubspot', name: 'HubSpot', detail: 'Sync notes and deals', soon: true },
  { key: 'linkedin', name: 'LinkedIn', detail: 'No compliant data path yet', soon: true },
]

export function IntegrationPlates() {
  return (
    <ul className="flex flex-col gap-2">
      {integrationPlates.map((p) => (
        <li key={p.key}>
          <Plate className="flex items-center justify-between gap-4 p-4 md:p-4">
            <div>
              <p className="text-base text-steel-100">{p.name}</p>
              <p className="text-sm text-steel-400">{p.detail}</p>
            </div>
            <Button disabled={p.soon}>{p.soon ? 'Available soon' : 'Connect'}</Button>
          </Plate>
        </li>
      ))}
    </ul>
  )
}

export function StepIntegrations({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const save = useOnboardingStep()
  const proceed = async () => {
    try {
      await save.mutateAsync({ step: 4 })
      onNext()
    } catch {
      toastError('Progress could not be saved', 'Check your connection and try again.')
    }
  }
  return (
    <div className="flex flex-col gap-6">
      <IntegrationPlates />
      <p className="text-sm text-steel-400">
        Gravv reads only the messages and events you allow, stores summaries rather than full
        mailboxes, and you can disconnect at any time from Settings. Nothing is shared with your
        organization unless you share it.
      </p>
      <div className="flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
        <Button variant="primary" loading={save.isPending} onClick={proceed}>
          Skip for now
        </Button>
      </div>
    </div>
  )
}
