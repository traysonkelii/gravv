import { Navigate, Outlet } from 'react-router'
import { useMe } from '@/lib/api/me'
import { useActiveWorkspace } from '@/lib/workspace'

export function RequireOnboarded() {
  const { data, isLoading, isError } = useMe()
  useActiveWorkspace()
  if (isLoading) return <div className="p-8 text-sm text-steel-400">Loading</div>
  if (isError || !data)
    return (
      <div className="p-8 text-sm text-rust-400">
        Your profile could not be loaded. Refresh to try again.
      </div>
    )
  if (data.profile.onboarding_step < 5) return <Navigate to="/onboarding" replace />
  return <Outlet />
}
