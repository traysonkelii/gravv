import { useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input, Select } from '@/components/ui/Field'
import { toast, toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import { useMe } from '@/lib/api/me'
import { formatDate } from '@/lib/format'
import { useActiveWorkspace } from '@/lib/workspace'
import {
  useInvitations,
  useInvite,
  useLeaveWorkspace,
  useMembers,
  useRevokeInvitation,
  useUpdateMember,
  type Member,
  type Role,
} from '@/features/settings/api'

const ROLES: Role[] = ['viewer', 'member', 'manager', 'admin', 'owner']
const rank = (r: string) => ROLES.indexOf(r as Role)

export function MembersSettings() {
  const { workspace } = useActiveWorkspace()
  const { data: me } = useMe()
  const id = workspace?.workspace_id ?? ''
  const members = useMembers(id || null)
  const invitations = useInvitations(id || null)
  const invite = useInvite(id)
  const revoke = useRevokeInvitation(id)
  const updateMember = useUpdateMember(id)
  const leave = useLeaveWorkspace()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('member')
  const [confirm, setConfirm] = useState<Member | null>(null)
  const [confirmLeave, setConfirmLeave] = useState(false)

  if (!workspace) return <p className="text-sm text-steel-400">Loading</p>
  if (workspace.kind === 'personal') {
    return (
      <p className="text-base text-steel-300">
        Your personal workspace has no members. Create an organization from the Workspace tab to
        invite people.
      </p>
    )
  }
  const myRole = workspace.role
  const isAdmin = rank(myRole) >= rank('admin')
  const assignable = ROLES.filter((r) => rank(r) < rank(myRole))

  return (
    <div className="flex flex-col gap-8">
      {isAdmin && (
        <form
          className="flex flex-col gap-2 md:flex-row md:items-end"
          onSubmit={async (e) => {
            e.preventDefault()
            try {
              await invite.mutateAsync({ email, role })
              setEmail('')
              toast('Invitation sent', `${email} will receive an email with a link.`)
            } catch (err) {
              toastError(
                'Invitation could not be sent',
                err instanceof ApiError ? err.problem.detail : undefined,
              )
            }
          }}
        >
          <Input
            label="Invite by email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="flex-1"
          />
          <Select
            label="Role"
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
            className="md:w-40"
          >
            {assignable.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </Select>
          <Button
            type="submit"
            variant="primary"
            loading={invite.isPending}
            loadingLabel="Sending..."
          >
            Send invitation
          </Button>
        </form>
      )}

      <section>
        <h2 className="text-md font-semibold text-steel-100">Members</h2>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-160 text-sm">
            <thead>
              <tr className="bg-steel-700 text-left text-steel-300">
                <th className="h-11 px-3 font-medium">Name</th>
                <th className="px-3 font-medium">Email</th>
                <th className="px-3 font-medium">Role</th>
                <th className="px-3 font-medium">Status</th>
                <th className="px-3 font-medium">Joined</th>
                <th className="px-3" />
              </tr>
            </thead>
            <tbody>
              {(members.data ?? []).map((m) => {
                const canEdit =
                  isAdmin &&
                  m.user_id !== me?.profile.id &&
                  rank(m.role) < rank(myRole) &&
                  m.status === 'active'
                return (
                  <tr key={m.user_id} className="h-11 border-b border-steel-600">
                    <td className="px-3 text-steel-100">
                      {m.full_name}
                      {m.role_title ? (
                        <span className="text-steel-400">, {m.role_title}</span>
                      ) : null}
                    </td>
                    <td className="px-3 text-steel-300">{m.email}</td>
                    <td className="px-3">
                      {canEdit ? (
                        <select
                          aria-label={`Role for ${m.full_name}`}
                          value={m.role}
                          onChange={(e) =>
                            updateMember.mutate({ userId: m.user_id, role: e.target.value as Role })
                          }
                          className="h-8 border border-steel-600 bg-steel-900 px-2 text-steel-100"
                        >
                          {assignable.map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>
                      ) : (
                        m.role
                      )}
                    </td>
                    <td className="px-3">
                      <Badge tone={m.status === 'departed' ? 'risk' : 'status'}>{m.status}</Badge>
                    </td>
                    <td className="tnum px-3 text-steel-400">{formatDate(m.joined_at)}</td>
                    <td className="px-3 text-right">
                      {canEdit && (
                        <Button variant="ghost" onClick={() => setConfirm(m)}>
                          Mark departed
                        </Button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      {isAdmin && (invitations.data?.length ?? 0) > 0 && (
        <section>
          <h2 className="text-md font-semibold text-steel-100">Pending invitations</h2>
          <ul className="mt-2 divide-y divide-steel-600">
            {invitations
              .data!.filter((i) => !i.accepted_at)
              .map((i) => (
                <li key={i.id} className="flex h-11 items-center justify-between text-sm">
                  <span className="text-steel-200">
                    {i.email}{' '}
                    <span className="text-steel-400">
                      as {i.role}, expires {formatDate(i.expires_at)}
                    </span>
                  </span>
                  <Button variant="ghost" onClick={() => revoke.mutate(i.id)}>
                    Revoke
                  </Button>
                </li>
              ))}
          </ul>
        </section>
      )}

      {myRole !== 'owner' && (
        <section className="border-t border-steel-600 pt-6">
          <Button variant="danger" onClick={() => setConfirmLeave(true)}>
            Leave workspace
          </Button>
        </section>
      )}

      <Dialog
        open={confirm !== null}
        title={`Mark ${confirm?.full_name ?? ''} as departed`}
        onClose={() => setConfirm(null)}
        confirmLabel="Mark departed"
        danger
        busy={updateMember.isPending}
        onConfirm={async () => {
          if (!confirm) return
          try {
            await updateMember.mutateAsync({ userId: confirm.user_id, status: 'departed' })
            toast('Member marked departed')
          } catch (e) {
            toastError(
              'Could not update member',
              e instanceof ApiError ? e.problem.detail : undefined,
            )
          }
          setConfirm(null)
        }}
      >
        They lose access to this workspace immediately; everything they created here stays with the
        organization.
      </Dialog>
      <Dialog
        open={confirmLeave}
        title="Leave this workspace"
        onClose={() => setConfirmLeave(false)}
        confirmLabel="Leave workspace"
        danger
        busy={leave.isPending}
        onConfirm={async () => {
          try {
            await leave.mutateAsync(id)
            toast('You left the workspace')
          } catch (e) {
            toastError('Could not leave', e instanceof ApiError ? e.problem.detail : undefined)
          }
          setConfirmLeave(false)
        }}
      >
        You lose access immediately. Your personal workspace is not affected.
      </Dialog>
    </div>
  )
}
