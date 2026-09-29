import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api/client'
import type { Schemas } from '@/lib/api/me'
import { useUiStore } from '@/lib/store'

export type Capture = Schemas['CaptureRead']
export type CaptureConfirm = Schemas['CaptureConfirm']
export type Extraction = Schemas['CaptureExtraction']
export type VoiceUpload = Schemas['VoiceUploadResponse']

const TERMINAL = new Set(['proposed', 'confirmed', 'discarded', 'failed'])

export function newIdempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, '')
}

export function useCapture(id: string | undefined) {
  return useQuery({
    queryKey: ['capture', id],
    enabled: !!id,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/captures/{capture_id}', { params: { path: { capture_id: id! } } }),
      ),
    refetchInterval: (q) => (q.state.data && TERMINAL.has(q.state.data.status) ? false : 2000),
  })
}

export function usePendingCaptures() {
  const workspaceId = useUiStore((s) => s.workspaceId)
  return useQuery({
    queryKey: ['captures', workspaceId],
    enabled: !!workspaceId,
    queryFn: async () => unwrap(await api.GET('/api/v1/captures')),
  })
}

export function useCreateTextCapture() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: {
      text: string
      contact_id?: string | null
      idempotency_key: string
    }) => unwrap(await api.POST('/api/v1/captures/text', { body })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['captures'] }),
  })
}

export function useVoiceUpload() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      blob,
      contentType,
      contactId,
      durationSeconds,
    }: {
      blob: Blob
      contentType: 'audio/webm' | 'audio/mp4' | 'audio/mpeg' | 'audio/wav'
      contactId?: string | null
      durationSeconds: number
    }) => {
      const signed = unwrap(
        await api.POST('/api/v1/captures/voice/upload-url', {
          body: {
            content_type: contentType,
            size_bytes: blob.size,
            contact_id: contactId ?? null,
            idempotency_key: newIdempotencyKey(),
          },
        }),
      )
      const put = await fetch(signed.upload_url, {
        method: 'PUT',
        body: blob,
        headers: signed.headers,
      })
      if (!put.ok)
        throw new Error('Recording could not be uploaded. Check your connection and try again.')
      return unwrap(
        await api.POST('/api/v1/captures/{capture_id}/uploaded', {
          params: { path: { capture_id: signed.capture_id } },
          body: { duration_seconds: Math.min(durationSeconds, 600) },
        }),
      )
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['captures'] }),
  })
}

export function useConfirmCapture(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: CaptureConfirm) =>
      unwrap(
        await api.POST('/api/v1/captures/{capture_id}/confirm', {
          params: { path: { capture_id: id } },
          body,
        }),
      ),
    onSuccess: () => void qc.invalidateQueries(),
  })
}

export function useDiscardCapture(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/v1/captures/{capture_id}/discard', {
          params: { path: { capture_id: id } },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['captures'] }),
  })
}
