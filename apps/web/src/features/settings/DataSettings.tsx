import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Field'
import { toast, toastError } from '@/components/ui/Toast'
import { api, ApiError, unwrap } from '@/lib/api/client'
import { useAuth } from '@/lib/auth'
import { formatDateTime, relativeTime } from '@/lib/format'
import { supabase } from '@/lib/supabase'
import { useActiveWorkspace } from '@/lib/workspace'

function useExports() {
  return useQuery({
    queryKey: ['exports'],
    queryFn: async () => unwrap(await api.GET('/api/v1/me/exports')),
    refetchInterval: (q) =>
      q.state.data?.some((e) => e.status === 'queued' || e.status === 'running') ? 2000 : false,
  })
}

export function DataSettings() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { workspace } = useActiveWorkspace()
  const exports = useExports()
  const request = useMutation({
    mutationFn: async (scope: 'personal' | 'my_contributions') =>
      unwrap(await api.POST('/api/v1/me/export', { body: { scope } })),
    onSuccess: () => {
      toast('Export started', 'It appears below when ready.')
      void qc.invalidateQueries({ queryKey: ['exports'] })
    },
    onError: (e) =>
      toastError(
        'Export could not be started',
        e instanceof ApiError ? e.problem.detail : undefined,
      ),
  })
  const [confirm, setConfirm] = useState(false)
  const [password, setPassword] = useState('')
  const [deleting, setDeleting] = useState(false)

  const deleteAccount = async () => {
    if (!user?.email) return
    setDeleting(true)
    const { error } = await supabase.auth.signInWithPassword({ email: user.email, password })
    if (error) {
      setDeleting(false)
      return toastError('Password did not match', 'Re-enter your password to confirm.')
    }
    const res = await api.DELETE('/api/v1/me')
    setDeleting(false)
    if (res.response.ok) {
      await supabase.auth.signOut()
      navigate('/auth/sign-in', { replace: true })
      return
    }
    const problem = res.error as { detail?: string } | undefined
    toastError('Account could not be deleted', problem?.detail)
  }

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h2 className="text-md font-semibold text-steel-100">Export</h2>
        <p className="text-sm text-steel-400">
          Exports are zipped JSON and CSV files. Links stay valid for seven days.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => request.mutate('personal')} loading={request.isPending}>
            Export my personal workspace
          </Button>
          {workspace?.kind === 'organization' && (
            <Button onClick={() => request.mutate('my_contributions')} loading={request.isPending}>
              Export my contributions to {workspace.workspace_name}
            </Button>
          )}
        </div>
        <ul className="divide-y divide-steel-600">
          {(exports.data ?? []).map((e) => (
            <li
              key={e.id}
              className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
            >
              <span className="text-steel-200">
                {e.scope.replace('_', ' ')}, requested {relativeTime(e.created_at)}
                <span className="text-steel-400">
                  , {e.status}
                  {e.expires_at ? `, expires ${formatDateTime(e.expires_at)}` : ''}
                </span>
              </span>
              {e.download_url && (
                <a href={e.download_url} className="text-steel-100 hover:text-steel-050">
                  Download
                </a>
              )}
              {e.error && <span className="text-rust-400">{e.error}</span>}
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-3 border-t border-steel-600 pt-6">
        <h2 className="text-md font-semibold text-steel-100">Delete account</h2>
        <p className="text-sm text-steel-400">
          Your personal workspace is deleted. Organizations keep what you created there, attributed
          to a former member. This cannot be undone.
        </p>
        <div>
          <Button variant="danger" onClick={() => setConfirm(true)}>
            Delete my account
          </Button>
        </div>
      </section>

      <Dialog
        open={confirm}
        title="Delete your account"
        onClose={() => setConfirm(false)}
        confirmLabel="Delete account"
        danger
        busy={deleting}
        onConfirm={deleteAccount}
      >
        <p>Enter your password to confirm. If you own an organization, transfer ownership first.</p>
        <div className="mt-3">
          <Input
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
      </Dialog>
    </div>
  )
}
