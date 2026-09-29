import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api/client'
import type { components } from '@/lib/api/schema'

export type Schemas = components['schemas']
export type Me = Schemas['MeRead']
export type MeUpdate = Schemas['MeUpdate']
export type OnboardingUpdate = Schemas['OnboardingUpdate']

export const meKey = ['me'] as const

export function useMe(enabled = true) {
  return useQuery({
    queryKey: meKey,
    enabled,
    queryFn: async () => unwrap(await api.GET('/api/v1/me')),
  })
}

export function useUpdateMe() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: MeUpdate) => unwrap(await api.PATCH('/api/v1/me', { body })),
    onSuccess: (me) => qc.setQueryData(meKey, me),
  })
}

export function useOnboardingStep() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: OnboardingUpdate) =>
      unwrap(await api.PATCH('/api/v1/me/onboarding', { body })),
    onSuccess: (me) => qc.setQueryData(meKey, me),
  })
}
