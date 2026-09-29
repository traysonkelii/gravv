import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Field'
import { AuthLayout } from '@/features/auth/AuthLayout'
import { supabase } from '@/lib/supabase'

const requestSchema = z.object({ email: z.email('Enter a valid email address') })
const updateSchema = z.object({ password: z.string().min(12, 'Use at least 12 characters') })

/* Two modes: request a reset email, or (arriving from the email with a recovery session) set a new password. */
export function Reset() {
  const navigate = useNavigate()
  const [recovery, setRecovery] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const request = useForm<z.infer<typeof requestSchema>>({ resolver: zodResolver(requestSchema) })
  const update = useForm<z.infer<typeof updateSchema>>({ resolver: zodResolver(updateSchema) })

  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'PASSWORD_RECOVERY') setRecovery(true)
    })
    return () => data.subscription.unsubscribe()
  }, [])

  if (recovery) {
    return (
      <AuthLayout title="Set a new password">
        <form
          onSubmit={update.handleSubmit(async ({ password }) => {
            const { error } = await supabase.auth.updateUser({ password })
            if (error) setError(error.message)
            else navigate('/app', { replace: true })
          })}
          className="flex flex-col gap-4"
          noValidate
        >
          <Input
            label="New password"
            type="password"
            autoComplete="new-password"
            {...update.register('password')}
            error={update.formState.errors.password?.message}
          />
          {error && (
            <p role="alert" className="text-sm text-rust-400">
              {error}
            </p>
          )}
          <Button type="submit" variant="primary" loading={update.formState.isSubmitting}>
            Save password
          </Button>
        </form>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout title="Reset your password">
      {sent ? (
        <p className="text-base text-steel-300">
          Check your inbox for a link to set a new password.
        </p>
      ) : (
        <form
          onSubmit={request.handleSubmit(async ({ email }) => {
            const { error } = await supabase.auth.resetPasswordForEmail(email, {
              redirectTo: `${window.location.origin}/auth/reset`,
            })
            if (error) setError('The email could not be sent. Check the address and try again.')
            else setSent(true)
          })}
          className="flex flex-col gap-4"
          noValidate
        >
          <Input
            label="Email"
            type="email"
            autoComplete="email"
            {...request.register('email')}
            error={request.formState.errors.email?.message}
          />
          {error && (
            <p role="alert" className="text-sm text-rust-400">
              {error}
            </p>
          )}
          <Button
            type="submit"
            variant="primary"
            loading={request.formState.isSubmitting}
            loadingLabel="Sending..."
          >
            Send reset link
          </Button>
        </form>
      )}
      <p className="mt-6 text-sm text-steel-400">
        <Link to="/auth/sign-in" className="text-steel-200 hover:text-steel-050">
          Back to sign in
        </Link>
      </p>
    </AuthLayout>
  )
}
