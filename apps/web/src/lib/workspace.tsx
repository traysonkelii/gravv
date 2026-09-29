import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useMe, type Me } from '@/lib/api/me'
import { useUiStore } from '@/lib/store'

export type Membership = Me['memberships'][number]

/* Keeps the active workspace id valid: falls back to the profile default when the stored id is missing
   or no longer an active membership. */
export function useActiveWorkspace(): { workspace: Membership | null; memberships: Membership[] } {
  const { data } = useMe()
  const workspaceId = useUiStore((s) => s.workspaceId)
  const setWorkspaceId = useUiStore((s) => s.setWorkspaceId)
  const memberships = (data?.memberships ?? []).filter((m) => m.status === 'active')
  const current = memberships.find((m) => m.workspace_id === workspaceId) ?? null
  useEffect(() => {
    if (!data) return
    if (current) return
    const fallback =
      memberships.find((m) => m.workspace_id === data.profile.default_workspace_id) ??
      memberships[0] ??
      null
    if (fallback) setWorkspaceId(fallback.workspace_id)
  }, [data, current, memberships, setWorkspaceId])
  return { workspace: current, memberships }
}

export function useSwitchWorkspace() {
  const qc = useQueryClient()
  const setWorkspaceId = useUiStore((s) => s.setWorkspaceId)
  return (id: string) => {
    setWorkspaceId(id)
    void qc.invalidateQueries()
  }
}
