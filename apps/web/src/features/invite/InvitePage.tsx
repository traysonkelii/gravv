import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router'
import { Button } from '@/components/ui/Button'
import { toastError } from '@/components/ui/Toast'
import { AuthLayout } from '@/features/auth/AuthLayout'
import { api, ApiError, unwrap } from '@/lib/api/client'
import { useAuth } from '@/lib/auth'
import { useSwitchWorkspace } from '@/lib/workspace'

export function InvitePage() {
  const { token = '' } = useParams()
  const { session, loading } = useAuth()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const switchTo = useSwitchWorkspace()
  const peek = useQuery({
    queryKey: ['invite', token],
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/invitations/{token}', { params: { path: { token } } })),
    retry: false,
  })
  const accept = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/v1/invitations/{token}/accept', { params: { path: { token } } })),
    onSuccess: async (res) => {
      await qc.invalidateQueries()
      switchTo(res.workspace_id)
      navigate('/app', { replace: true })
    },
    onError: (e) =>
      toastError(
        'Invitation could not be accepted',
        e instanceof ApiError ? e.problem.detail : undefined,
      ),
  })

  if (peek.isLoading || loading)
    return (
      <AuthLayout title="Checking invitation">
        <p className="text-steel-400">One moment.</p>
      </AuthLayout>
    )
  if (peek.isError || !peek.data) {
    return (
      <AuthLayout title="Invitation not found">
        <p className="text-base text-steel-300">
          This link is not valid. Ask the person who invited you to send a new one.
        </p>
      </AuthLayout>
    )
  }
  const inv = peek.data
  const next = `/invite/${token}`
  return (
    <AuthLayout title={`Join ${inv.workspace_name}`}>
      <p className="text-base text-steel-300">
        {inv.inviter_name} invited {inv.email} to join as {inv.role}.
      </p>
      {inv.accepted ? (
        <p className="mt-4 text-sm text-steel-400">This invitation was already accepted.</p>
      ) : inv.expired ? (
        <p className="mt-4 text-sm text-rust-400">
          This invitation has expired. Ask for a new one.
        </p>
      ) : session ? (
        <div className="mt-6 flex flex-col gap-3">
          {session.user.email?.toLowerCase() !== inv.email.toLowerCase() && (
            <p className="text-sm text-rust-400">
              You are signed in as {session.user.email}. Sign in with {inv.email} to accept.
            </p>
          )}
          <Button
            variant="primary"
            loading={accept.isPending}
            loadingLabel="Joining..."
            onClick={() => accept.mutate()}
          >
            Accept invitation
          </Button>
        </div>
      ) : (
        <div className="mt-6 flex flex-col gap-3">
          <Link
            to="/auth/sign-in"
            state={{ from: next }}
            className="text-steel-200 hover:text-steel-050"
          >
            Sign in to accept
          </Link>
          <Link
            to="/auth/sign-up"
            state={{ from: next, email: inv.email }}
            className="text-steel-200 hover:text-steel-050"
          >
            Create an account with {inv.email}
          </Link>
        </div>
      )}
    </AuthLayout>
  )
}
