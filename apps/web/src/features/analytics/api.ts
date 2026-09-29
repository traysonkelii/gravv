import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api/client'
import type { Schemas } from '@/lib/api/me'
import { useUiStore } from '@/lib/store'

export type Summary = Schemas['AnalyticsSummary']
export type Insight = Schemas['InsightRead']
export type Range = 'today' | 'week' | 'month' | 'quarter' | 'year'
export type Scope = 'me' | 'team'

export function useSummary(range: Range, scope: Scope) {
  const ws = useUiStore((s) => s.workspaceId)
  return useQuery({
    queryKey: ['analytics', ws, 'summary', range, scope],
    enabled: !!ws,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/analytics/summary', { params: { query: { range, scope } } })),
  })
}

export function useDistribution(scope: Scope) {
  const ws = useUiStore((s) => s.workspaceId)
  return useQuery({
    queryKey: ['analytics', ws, 'distribution', scope],
    enabled: !!ws,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/analytics/distribution', { params: { query: { scope } } })),
  })
}

export function useInteractionSeries(range: Range, scope: Scope) {
  const ws = useUiStore((s) => s.workspaceId)
  return useQuery({
    queryKey: ['analytics', ws, 'interactions', range, scope],
    enabled: !!ws,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/analytics/interactions', { params: { query: { range, scope } } }),
      ),
  })
}

export function useTopContacts(scope: Scope, q: string) {
  const ws = useUiStore((s) => s.workspaceId)
  return useQuery({
    queryKey: ['analytics', ws, 'top', scope, q],
    enabled: !!ws,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/analytics/top-contacts', {
          params: { query: { scope, q: q || undefined, limit: 10 } },
        }),
      ),
  })
}

export function useTeam(range: Range, enabled: boolean) {
  const ws = useUiStore((s) => s.workspaceId)
  return useQuery({
    queryKey: ['analytics', ws, 'team', range],
    enabled: !!ws && enabled,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/analytics/team', { params: { query: { range } } })),
  })
}

export type InsightFilter = 'new' | 'seen' | 'acted' | 'dismissed' | 'all'

export function useInsights(scope: Scope, status: InsightFilter = 'new', limit = 50) {
  const ws = useUiStore((s) => s.workspaceId)
  const statusParam = status === 'all' ? undefined : status
  return useQuery({
    queryKey: ['insights', ws, scope, status, limit],
    enabled: !!ws,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/insights', {
          params: { query: { scope, status: statusParam, limit } },
        }),
      ),
  })
}

export function useInsightStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, status }: { id: string; status: 'seen' | 'acted' | 'dismissed' }) =>
      unwrap(
        await api.POST('/api/v1/insights/{insight_id}/status', {
          params: { path: { insight_id: id } },
          body: { status },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['insights'] }),
  })
}

export function useInsightAct() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST('/api/v1/insights/{insight_id}/act', {
          params: { path: { insight_id: id } },
        }),
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['insights'] })
      void qc.invalidateQueries({ queryKey: ['contacts'] })
    },
  })
}

export function useGenerateInsights() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/v1/insights/generate')),
    onSuccess: () => setTimeout(() => void qc.invalidateQueries({ queryKey: ['insights'] }), 2500),
  })
}
