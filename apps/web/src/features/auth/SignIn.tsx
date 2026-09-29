import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Field'
import { AuthLayout } from '@/features/auth/AuthLayout'
import { supabase } from '@/lib/supabase'

const schema = z.object({
  email: z.email('Enter a valid email address'),
  password: z.string().min(1, 'Enter your password'),
})
type Form = z.infer<typeof schema>

export function SignIn() {
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/app'
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState } = useForm<Form>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: Form) => {
    setError(null)
    const { error } = await supabase.auth.signInWithPassword(values)
    if (error) {
      setError('Email or password is incorrect. Check both and try again.')
      return
    }
    navigate(from, { replace: true })
  }

  return (
    <AuthLayout title="Sign in">
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
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
          autoComplete="current-password"
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
          loadingLabel="Signing in..."
        >
          Sign in
        </Button>
      </form>
      <div className="mt-6 flex flex-col gap-2 text-sm text-steel-400">
        <Link to="/auth/magic-link" className="text-steel-200 hover:text-steel-050">
          Email me a sign-in link
        </Link>
        <Link to="/auth/reset" className="text-steel-200 hover:text-steel-050">
          Forgot password
        </Link>
        <p>
          New here?{' '}
          <Link to="/auth/sign-up" className="text-steel-200 hover:text-steel-050">
            Create an account
          </Link>
        </p>
      </div>
    </AuthLayout>
  )
}
