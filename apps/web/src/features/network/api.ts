import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api/client'
import type { Schemas } from '@/lib/api/me'
import { useUiStore } from '@/lib/store'

export type Graph = Schemas['Graph']
export type GraphNode = Schemas['GraphNode']
export type GraphEdge = Schemas['GraphEdge']
export type PathsResult = Schemas['PathsResult']
export type GraphFilters = { relationship_type?: string; industry?: string; min_score?: number }

export function useGraph(filters: GraphFilters) {
  const ws = useUiStore((s) => s.workspaceId)
  return useQuery({
    queryKey: ['network', ws, filters],
    enabled: !!ws,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/network/graph', { params: { query: filters } })),
  })
}

export function usePaths(from: string, to: string | null) {
  const ws = useUiStore((s) => s.workspaceId)
  return useQuery({
    queryKey: ['network-paths', ws, from, to],
    enabled: !!ws && !!to,
    retry: false,
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/network/paths', { params: { query: { from, to: to! } } })),
  })
}
