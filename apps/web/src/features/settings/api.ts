import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api/client'
import { meKey, type Schemas } from '@/lib/api/me'

export type Workspace = Schemas['WorkspaceRead']
export type WorkspaceUpdate = Schemas['WorkspaceUpdate']
export type WorkspaceCreate = Schemas['WorkspaceCreate']
export type Member = Schemas['MemberRead']
export type Invitation = Schemas['InvitationRead']
export type Role = Schemas['WorkspaceRole']

export function useWorkspace(id: string | null) {
  return useQuery({
    queryKey: ['workspace', id],
    enabled: !!id,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/workspaces/{workspace_id}', {
          params: { path: { workspace_id: id! } },
        }),
      ),
  })
}

export function useUpdateWorkspace(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: WorkspaceUpdate) =>
      unwrap(
        await api.PATCH('/api/v1/workspaces/{workspace_id}', {
          params: { path: { workspace_id: id } },
          body,
        }),
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['workspace', id] })
      void qc.invalidateQueries({ queryKey: meKey })
    },
  })
}

export function useCreateWorkspace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: WorkspaceCreate) =>
      unwrap(await api.POST('/api/v1/workspaces', { body })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: meKey }),
  })
}

export function useMembers(id: string | null) {
  return useQuery({
    queryKey: ['members', id],
    enabled: !!id,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/workspaces/{workspace_id}/members', {
          params: { path: { workspace_id: id! } },
        }),
      ),
  })
}

export function useUpdateMember(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ userId, ...body }: { userId: string; role?: Role; status?: 'departed' }) =>
      unwrap(
        await api.PATCH('/api/v1/workspaces/{workspace_id}/members/{user_id}', {
          params: { path: { workspace_id: id, user_id: userId } },
          body,
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['members', id] }),
  })
}

export function useLeaveWorkspace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.DELETE('/api/v1/workspaces/{workspace_id}/members/me', {
          params: { path: { workspace_id: id } },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries(),
  })
}

export function useInvitations(id: string | null) {
  return useQuery({
    queryKey: ['invitations', id],
    enabled: !!id,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/workspaces/{workspace_id}/invitations', {
          params: { path: { workspace_id: id! } },
        }),
      ),
  })
}

export function useInvite(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { email: string; role: Role }) =>
      unwrap(
        await api.POST('/api/v1/workspaces/{workspace_id}/invitations', {
          params: { path: { workspace_id: id } },
          body,
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['invitations', id] }),
  })
}

export function useRevokeInvitation(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (invitationId: string) =>
      unwrap(
        await api.DELETE('/api/v1/workspaces/{workspace_id}/invitations/{invitation_id}', {
          params: { path: { workspace_id: id, invitation_id: invitationId } },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['invitations', id] }),
  })
}
