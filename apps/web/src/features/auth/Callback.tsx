import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { AuthLayout } from '@/features/auth/AuthLayout'
import { supabase } from '@/lib/supabase'

/* OAuth and email-link landing. supabase-js exchanges the code from the URL; we wait for a session. */
export function Callback() {
  const navigate = useNavigate()
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let done = false
    const finish = () => {
      if (done) return
      done = true
      navigate('/app', { replace: true })
    }
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) finish()
    })
    const { data } = supabase.auth.onAuthStateChange((_e, session) => {
      if (session) finish()
    })
    const timer = setTimeout(() => {
      if (!done) setFailed(true)
    }, 8000)
    return () => {
      data.subscription.unsubscribe()
      clearTimeout(timer)
    }
  }, [navigate])
  return (
    <AuthLayout title={failed ? 'Sign-in link did not work' : 'Signing you in'}>
      <p className="text-base text-steel-300">
        {failed
          ? 'The link may have expired. Request a new one from the sign-in page.'
          : 'One moment.'}
      </p>
    </AuthLayout>
  )
}
