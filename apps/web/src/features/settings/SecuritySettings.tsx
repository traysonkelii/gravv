import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Field'
import { toast, toastError } from '@/components/ui/Toast'
import { supabase } from '@/lib/supabase'

type Factor = { id: string; friendly_name?: string; factor_type: string; status: string }

export function SecuritySettings() {
  const [password, setPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [enroll, setEnroll] = useState<{ id: string; qr: string; secret: string } | null>(null)
  const [code, setCode] = useState('')
  const qc = useQueryClient()
  const factorsQuery = useQuery({
    queryKey: ['mfa-factors'],
    queryFn: async () => ((await supabase.auth.mfa.listFactors()).data?.totp ?? []) as Factor[],
  })
  const factors = factorsQuery.data ?? []
  const reloadFactors = () => qc.invalidateQueries({ queryKey: ['mfa-factors'] })

  const changePassword = async () => {
    setSaving(true)
    const { error } = await supabase.auth.updateUser({ password })
    setSaving(false)
    if (error) toastError('Password could not be changed', error.message)
    else {
      setPassword('')
      toast('Password changed')
    }
  }

  const startEnroll = async () => {
    const { data, error } = await supabase.auth.mfa.enroll({
      factorType: 'totp',
      friendlyName: 'Authenticator app',
    })
    if (error || !data) return toastError('Could not start enrollment', error?.message)
    setEnroll({ id: data.id, qr: data.totp.qr_code, secret: data.totp.secret })
  }

  const verifyEnroll = async () => {
    if (!enroll) return
    const { data: ch, error: chErr } = await supabase.auth.mfa.challenge({ factorId: enroll.id })
    if (chErr || !ch) return toastError('Could not verify', chErr?.message)
    const { error } = await supabase.auth.mfa.verify({
      factorId: enroll.id,
      challengeId: ch.id,
      code,
    })
    if (error)
      return toastError('Code did not match', 'Enter the current six-digit code from your app.')
    setEnroll(null)
    setCode('')
    toast('Two-factor authentication enabled')
    await reloadFactors()
  }

  const unenroll = async (id: string) => {
    const { error } = await supabase.auth.mfa.unenroll({ factorId: id })
    if (error) toastError('Could not remove factor', error.message)
    else {
      toast('Two-factor authentication removed')
      await reloadFactors()
    }
  }

  const verified = factors.filter((f) => f.status === 'verified')
  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h2 className="text-md font-semibold text-steel-100">Password</h2>
        <Input
          label="New password"
          type="password"
          autoComplete="new-password"
          hint="At least 12 characters."
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <div>
          <Button
            variant="primary"
            disabled={password.length < 12}
            loading={saving}
            onClick={changePassword}
          >
            Change password
          </Button>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-md font-semibold text-steel-100">Two-factor authentication</h2>
        {verified.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {verified.map((f) => (
              <li
                key={f.id}
                className="flex items-center justify-between border border-steel-600 px-3 py-2 text-sm"
              >
                <span className="text-steel-200">{f.friendly_name ?? 'Authenticator app'}</span>
                <Button variant="ghost" onClick={() => unenroll(f.id)}>
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        ) : enroll ? (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-steel-300">
              Scan this code with your authenticator app, then enter the six-digit code.
            </p>
            <div
              className="w-48 bg-steel-050 p-2"
              dangerouslySetInnerHTML={{ __html: enroll.qr }}
            />
            <p className="tnum text-sm text-steel-400">Manual key: {enroll.secret}</p>
            <Input
              label="Code"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-40"
            />
            <div className="flex gap-2">
              <Button variant="primary" disabled={code.length < 6} onClick={verifyEnroll}>
                Verify and enable
              </Button>
              <Button variant="ghost" onClick={() => setEnroll(null)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div>
            <p className="mb-3 text-sm text-steel-400">
              Adds a code from an authenticator app at sign-in. Required for ownership transfers.
            </p>
            <Button onClick={startEnroll}>Set up authenticator app</Button>
          </div>
        )}
      </section>
    </div>
  )
}
