import { IntegrationPlates } from '@/features/onboarding/StepIntegrations'

export function IntegrationsSettings() {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-steel-400">
        Connections are per user. Email, calendar, and CRM sync arrive in a later release.
      </p>
      <IntegrationPlates />
    </div>
  )
}
