import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Field'
import { AuthLayout } from '@/features/auth/AuthLayout'
import { supabase } from '@/lib/supabase'

const schema = z.object({
  full_name: z.string().min(1, 'Enter your name').max(120),
  email: z.email('Enter a valid email address'),
  password: z.string().min(12, 'Use at least 12 characters'),
})
type Form = z.infer<typeof schema>

export function SignUp() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [checkInbox, setCheckInbox] = useState(false)
  const { register, handleSubmit, formState } = useForm<Form>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: Form) => {
    setError(null)
    const { data, error } = await supabase.auth.signUp({
      email: values.email,
      password: values.password,
      options: {
        data: { full_name: values.full_name },
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    })
    if (error) {
      setError(error.message)
      return
    }
    if (data.session) navigate('/onboarding', { replace: true })
    else setCheckInbox(true)
  }

  if (checkInbox) {
    return (
      <AuthLayout title="Check your inbox">
        <p className="text-base text-steel-300">
          We sent a confirmation link to your email. Open it to finish creating your account.
        </p>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout title="Create your account">
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
        <Input
          label="Full name"
          autoComplete="name"
          {...register('full_name')}
          error={formState.errors.full_name?.message}
        />
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          {...register('email')}
          error={formState.errors.email?.message}
        />
        <Input
          label="Password"
          type="password"
          autoComplete="new-password"
          hint="At least 12 characters."
          {...register('password')}
          error={formState.errors.password?.message}
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
          loadingLabel="Creating account..."
        >
          Create account
        </Button>
      </form>
      <p className="mt-6 text-sm text-steel-400">
        Already have an account?{' '}
        <Link to="/auth/sign-in" className="text-steel-200 hover:text-steel-050">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  )
}
