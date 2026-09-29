import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api/client'
import type { Schemas } from '@/lib/api/me'
import { useUiStore } from '@/lib/store'

export type Task = Schemas['TaskRead']
export type TaskCreate = Schemas['TaskCreate']
export type TaskUpdate = Schemas['TaskUpdate']

export function useTasks(filters: {
  status?: 'open' | 'done' | 'snoozed' | 'cancelled'
  contact_id?: string
  assignee?: 'me'
}) {
  const ws = useUiStore((s) => s.workspaceId)
  return useInfiniteQuery({
    queryKey: ['tasks', ws, filters],
    enabled: !!ws,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET('/api/v1/tasks', {
          params: { query: { ...filters, limit: 50, cursor: pageParam } },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ['tasks'] })
  void qc.invalidateQueries({ queryKey: ['contact'] })
  void qc.invalidateQueries({ queryKey: ['contacts'] })
  void qc.invalidateQueries({ queryKey: ['timeline'] })
  void qc.invalidateQueries({ queryKey: ['analytics'] })
}

export function useCreateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: TaskCreate) => unwrap(await api.POST('/api/v1/tasks', { body })),
    onSuccess: () => invalidate(qc),
  })
}

export function useUpdateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }: TaskUpdate & { id: string }) =>
      unwrap(
        await api.PATCH('/api/v1/tasks/{task_id}', { params: { path: { task_id: id } }, body }),
      ),
    onSuccess: () => invalidate(qc),
  })
}

/* Complete and snooze are optimistic: the row moves immediately and rolls back on error. */
export function useCompleteTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST('/api/v1/tasks/{task_id}/complete', { params: { path: { task_id: id } } }),
      ),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['tasks'] })
      const snapshots = qc.getQueriesData<{ pages: { items: Task[] }[] }>({ queryKey: ['tasks'] })
      qc.setQueriesData<{ pages: { items: Task[] }[] }>({ queryKey: ['tasks'] }, (old) =>
        old
          ? {
              ...old,
              pages: old.pages.map((p) => ({
                ...p,
                items: p.items.map((t) =>
                  t.id === id
                    ? { ...t, status: 'done', completed_at: new Date().toISOString() }
                    : t,
                ),
              })),
            }
          : old,
      )
      return { snapshots }
    },
    onError: (_e, _id, ctx) => ctx?.snapshots.forEach(([key, data]) => qc.setQueryData(key, data)),
    onSettled: () => invalidate(qc),
  })
}

export function useSnoozeTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, until }: { id: string; until: string }) =>
      unwrap(
        await api.POST('/api/v1/tasks/{task_id}/snooze', {
          params: { path: { task_id: id } },
          body: { until },
        }),
      ),
    onMutate: async ({ id, until }) => {
      await qc.cancelQueries({ queryKey: ['tasks'] })
      const snapshots = qc.getQueriesData<{ pages: { items: Task[] }[] }>({ queryKey: ['tasks'] })
      qc.setQueriesData<{ pages: { items: Task[] }[] }>({ queryKey: ['tasks'] }, (old) =>
        old
          ? {
              ...old,
              pages: old.pages.map((p) => ({
                ...p,
                items: p.items.map((t) =>
                  t.id === id
                    ? { ...t, status: 'snoozed', due_at: until, snoozed_until: until }
                    : t,
                ),
              })),
            }
          : old,
      )
      return { snapshots }
    },
    onError: (_e, _v, ctx) => ctx?.snapshots.forEach(([key, data]) => qc.setQueryData(key, data)),
    onSettled: () => invalidate(qc),
  })
}
