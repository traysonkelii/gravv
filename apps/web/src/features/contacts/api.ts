import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api/client'
import type { Schemas } from '@/lib/api/me'
import { useUiStore } from '@/lib/store'

export type Contact = Schemas['ContactRead']
export type ContactCreate = Schemas['ContactCreate']
export type ContactUpdate = Schemas['ContactUpdate']
export type Fact = Schemas['FactRead']
export type FactCreate = Schemas['FactCreate']
export type Interaction = Schemas['InteractionRead']
export type InteractionCreate = Schemas['InteractionCreate']
export type TimelineEntry = Schemas['TimelineEntry']
export type Company = Schemas['CompanyRead']

export type ContactFilters = {
  q?: string
  status?: string
  band?: 'strong' | 'steady' | 'weak' | 'drifting'
  relationship_type?: string
  company_id?: string
  tag?: string
  owner?: 'me'
  sort?: 'updated' | 'gravity' | 'last_interaction' | 'name' | 'next_due'
}

function ws(): string {
  return useUiStore.getState().workspaceId ?? ''
}

export function useContacts(filters: ContactFilters) {
  const workspaceId = useUiStore((s) => s.workspaceId)
  return useInfiniteQuery({
    queryKey: ['contacts', workspaceId, filters],
    enabled: !!workspaceId,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET('/api/v1/contacts', {
          params: { query: { ...filters, limit: 25, cursor: pageParam } },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })
}

export function useContact(id: string | undefined) {
  const workspaceId = useUiStore((s) => s.workspaceId)
  return useQuery({
    queryKey: ['contact', workspaceId, id],
    enabled: !!workspaceId && !!id,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/contacts/{contact_id}', { params: { path: { contact_id: id! } } }),
      ),
  })
}

export function useCreateContact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: ContactCreate) => unwrap(await api.POST('/api/v1/contacts', { body })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['contacts', ws()] }),
  })
}

export function useUpdateContact(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: ContactUpdate) =>
      unwrap(
        await api.PATCH('/api/v1/contacts/{contact_id}', {
          params: { path: { contact_id: id } },
          body,
        }),
      ),
    onSuccess: (contact) => {
      qc.setQueryData(['contact', ws(), id], contact)
      void qc.invalidateQueries({ queryKey: ['contacts', ws()] })
    },
  })
}

export function useDeleteContact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.DELETE('/api/v1/contacts/{contact_id}', { params: { path: { contact_id: id } } }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['contacts', ws()] }),
  })
}

export function useShareContact(id: string) {
  return useMutation({
    mutationFn: async (target_workspace_id: string) =>
      unwrap(
        await api.POST('/api/v1/contacts/{contact_id}/share', {
          params: { path: { contact_id: id } },
          body: { target_workspace_id },
        }),
      ),
  })
}

export function useCopyToPersonal(id: string) {
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/v1/contacts/{contact_id}/copy-to-personal', {
          params: { path: { contact_id: id } },
        }),
      ),
  })
}

export function useTimeline(contactId: string | undefined, kinds: string[] | undefined) {
  const workspaceId = useUiStore((s) => s.workspaceId)
  return useInfiniteQuery({
    queryKey: ['timeline', workspaceId, contactId, kinds ?? []],
    enabled: !!workspaceId && !!contactId,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET('/api/v1/contacts/{contact_id}/timeline', {
          params: {
            path: { contact_id: contactId! },
            query: { kinds, limit: 25, cursor: pageParam },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })
}

export function useFacts(contactId: string | undefined, includeInactive: boolean) {
  const workspaceId = useUiStore((s) => s.workspaceId)
  return useQuery({
    queryKey: ['facts', workspaceId, contactId, includeInactive],
    enabled: !!workspaceId && !!contactId,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/contacts/{contact_id}/facts', {
          params: {
            path: { contact_id: contactId! },
            query: { include_inactive: includeInactive },
          },
        }),
      ),
  })
}

function invalidateContact(qc: ReturnType<typeof useQueryClient>, contactId: string) {
  void qc.invalidateQueries({ queryKey: ['facts', ws(), contactId] })
  void qc.invalidateQueries({ queryKey: ['timeline', ws(), contactId] })
  void qc.invalidateQueries({ queryKey: ['contact', ws(), contactId] })
  void qc.invalidateQueries({ queryKey: ['contacts', ws()] })
}

export function useCreateFact(contactId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: FactCreate) =>
      unwrap(
        await api.POST('/api/v1/contacts/{contact_id}/facts', {
          params: { path: { contact_id: contactId } },
          body,
        }),
      ),
    onSuccess: () => invalidateContact(qc, contactId),
  })
}

export function useUpdateFact(contactId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      ...body
    }: {
      id: string
      content?: string
      category?: Fact['category']
    }) =>
      unwrap(
        await api.PATCH('/api/v1/facts/{fact_id}', { params: { path: { fact_id: id } }, body }),
      ),
    onSuccess: () => invalidateContact(qc, contactId),
  })
}

export function useDeleteFact(contactId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(await api.DELETE('/api/v1/facts/{fact_id}', { params: { path: { fact_id: id } } })),
    onSuccess: () => invalidateContact(qc, contactId),
  })
}

export function useCreateInteraction(contactId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: InteractionCreate) =>
      unwrap(await api.POST('/api/v1/interactions', { body })),
    onSuccess: () => invalidateContact(qc, contactId),
  })
}

export function useDeleteInteraction(contactId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.DELETE('/api/v1/interactions/{interaction_id}', {
          params: { path: { interaction_id: id } },
        }),
      ),
    onSuccess: () => invalidateContact(qc, contactId),
  })
}

export function useCompanies(q?: string) {
  const workspaceId = useUiStore((s) => s.workspaceId)
  return useQuery({
    queryKey: ['companies', workspaceId, q ?? ''],
    enabled: !!workspaceId,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/companies', { params: { query: { q, limit: 100 } } })),
  })
}
