import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { Progress } from '@/components/ui/Progress'
import { useMe, type Me } from '@/lib/api/me'
import { copy } from '@/lib/copy'
import { StepProfile } from '@/features/onboarding/StepProfile'
import { StepInterests } from '@/features/onboarding/StepInterests'
import { StepGoals } from '@/features/onboarding/StepGoals'
import { StepIntegrations } from '@/features/onboarding/StepIntegrations'
import { StepDone } from '@/features/onboarding/StepDone'

const titles = [
  'About you',
  'What you follow',
  'What you want from Gravv',
  'Connect your tools',
  'Ready',
]

export function Onboarding() {
  const { data: me, isLoading } = useMe()
  if (isLoading || !me) return <div className="p-8 text-sm text-steel-400">Loading</div>
  if (me.profile.onboarding_step >= 5) return <Navigate to="/app" replace />
  return <Wizard me={me} />
}

function Wizard({ me }: { me: Me }) {
  const navigate = useNavigate()
  const [step, setStep] = useState<number>(() => Math.min(me.profile.onboarding_step + 1, 5))
  const next = () => setStep((s) => Math.min(s + 1, 5))
  const back = () => setStep((s) => Math.max(s - 1, 1))

  return (
    <main className="mx-auto w-full max-w-lg px-4 py-10">
      <p className="font-display text-xl font-bold text-steel-100">{copy.appName}</p>
      <div className="mt-6">
        <Progress steps={5} current={step} />
      </div>
      <p className="mt-2 text-sm text-steel-400">Step {step} of 5</p>
      <h1 className="mt-4 font-display text-2xl font-bold text-steel-100">{titles[step - 1]}</h1>
      <div className="mt-6">
        {step === 1 && <StepProfile me={me} onNext={next} />}
        {step === 2 && <StepInterests me={me} onNext={next} onBack={back} />}
        {step === 3 && <StepGoals me={me} onNext={next} onBack={back} />}
        {step === 4 && <StepIntegrations onNext={next} onBack={back} />}
        {step === 5 && <StepDone onDone={() => navigate('/app', { replace: true })} />}
      </div>
    </main>
  )
}
