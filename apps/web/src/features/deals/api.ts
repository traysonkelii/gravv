import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api/client'
import type { Schemas } from '@/lib/api/me'
import { useUiStore } from '@/lib/store'

export type Opportunity = Schemas['OpportunityRead']
export type OpportunityCreate = Schemas['OpportunityCreate']
export type OpportunityUpdate = Schemas['OpportunityUpdate']
export type OpportunityRole = Schemas['OpportunityRole']

export function useOpportunities(filters: {
  status?: 'open' | 'won' | 'lost' | 'on_hold'
  company_id?: string
  owner?: 'me'
}) {
  const ws = useUiStore((s) => s.workspaceId)
  return useInfiniteQuery({
    queryKey: ['opportunities', ws, filters],
    enabled: !!ws,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET('/api/v1/opportunities', {
          params: { query: { ...filters, limit: 50, cursor: pageParam } },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })
}

export function useOpportunity(id: string | undefined) {
  const ws = useUiStore((s) => s.workspaceId)
  return useQuery({
    queryKey: ['opportunity', ws, id],
    enabled: !!ws && !!id,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/opportunities/{opportunity_id}', {
          params: { path: { opportunity_id: id! } },
        }),
      ),
  })
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ['opportunities'] })
  void qc.invalidateQueries({ queryKey: ['opportunity'] })
  void qc.invalidateQueries({ queryKey: ['contact'] })
  void qc.invalidateQueries({ queryKey: ['analytics'] })
}

export function useCreateOpportunity() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: OpportunityCreate) =>
      unwrap(await api.POST('/api/v1/opportunities', { body })),
    onSuccess: () => invalidate(qc),
  })
}

export function useUpdateOpportunity() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }: OpportunityUpdate & { id: string }) =>
      unwrap(
        await api.PATCH('/api/v1/opportunities/{opportunity_id}', {
          params: { path: { opportunity_id: id } },
          body,
        }),
      ),
    onSuccess: () => invalidate(qc),
  })
}

export function useDeleteOpportunity() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.DELETE('/api/v1/opportunities/{opportunity_id}', {
          params: { path: { opportunity_id: id } },
        }),
      ),
    onSuccess: () => invalidate(qc),
  })
}

export function usePutOpportunityContact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      contactId,
      role,
    }: {
      id: string
      contactId: string
      role: OpportunityRole
    }) =>
      unwrap(
        await api.PUT('/api/v1/opportunities/{opportunity_id}/contacts/{contact_id}', {
          params: { path: { opportunity_id: id, contact_id: contactId } },
          body: { role },
        }),
      ),
    onSuccess: () => invalidate(qc),
  })
}

export function useRemoveOpportunityContact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, contactId }: { id: string; contactId: string }) =>
      unwrap(
        await api.DELETE('/api/v1/opportunities/{opportunity_id}/contacts/{contact_id}', {
          params: { path: { opportunity_id: id, contact_id: contactId } },
        }),
      ),
    onSuccess: () => invalidate(qc),
  })
}
