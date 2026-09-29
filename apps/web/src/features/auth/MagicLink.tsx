import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Field'
import { AuthLayout } from '@/features/auth/AuthLayout'
import { supabase } from '@/lib/supabase'

const schema = z.object({ email: z.email('Enter a valid email address') })
type Form = z.infer<typeof schema>

export function MagicLink() {
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState } = useForm<Form>({ resolver: zodResolver(schema) })

  const onSubmit = async ({ email }: Form) => {
    setError(null)
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    })
    if (error) setError('The link could not be sent. Check the address and try again.')
    else setSent(true)
  }

  return (
    <AuthLayout title="Sign in with a link">
      {sent ? (
        <p className="text-base text-steel-300">
          Check your inbox. The link signs you in on this device.
        </p>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
          <Input
            label="Email"
            type="email"
            autoComplete="email"
            {...register('email')}
            error={formState.errors.email?.message}
          />
          {error && (
            <p role="alert" className="text-sm text-rust-400">
              {error}
            </p>
          )}
          <Button
            type="submit"
            variant="primary"
            loading={formState.isSubmitting}
            loadingLabel="Sending..."
          >
            Send link
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
