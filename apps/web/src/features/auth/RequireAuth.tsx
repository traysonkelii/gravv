import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '@/lib/auth'

export function RequireAuth() {
  const { session, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="p-8 text-sm text-steel-400">Loading</div>
  if (!session) return <Navigate to="/auth/sign-in" replace state={{ from: location.pathname }} />
  return <Outlet />
}

export function RedirectIfAuthed() {
  const { session, loading } = useAuth()
  const location = useLocation()
  if (loading) return null
  if (session)
    return <Navigate to={(location.state as { from?: string } | null)?.from ?? '/app'} replace />
  return <Outlet />
}
