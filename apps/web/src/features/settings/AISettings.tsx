import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Field'
import { Plate } from '@/components/ui/Plate'
import { toast, toastError } from '@/components/ui/Toast'
import { api, ApiError, unwrap } from '@/lib/api/client'
import type { Schemas } from '@/lib/api/me'
import { formatDate } from '@/lib/format'
import { useActiveWorkspace } from '@/lib/workspace'

type Provider = 'anthropic' | 'openai' | 'deepgram'
type Status = Schemas['AIStatusRead']

const providers: {
  key: Provider
  name: string
  purpose: string
  placeholder: string
  modelHint?: string
}[] = [
  {
    key: 'anthropic',
    name: 'Anthropic',
    purpose: 'Extraction, profiles, and briefs.',
    placeholder: 'sk-ant-...',
    modelHint: 'Default claude-opus-5',
  },
  {
    key: 'openai',
    name: 'OpenAI',
    purpose: 'Whisper transcription, and extraction when no Anthropic key is set.',
    placeholder: 'sk-...',
    modelHint: 'Chat model, optional',
  },
  {
    key: 'deepgram',
    name: 'Deepgram',
    purpose: 'Voice transcription, preferred over Whisper when both are set.',
    placeholder: 'Deepgram key',
  },
]

export function useAIStatus(workspaceId: string | null) {
  return useQuery({
    queryKey: ['ai-status', workspaceId],
    enabled: !!workspaceId,
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/workspaces/{workspace_id}/ai', {
          params: { path: { workspace_id: workspaceId! } },
        }),
      ),
  })
}

function sourceLabel(s: Status['llm']): string {
  if (!s.configured) return 'Not configured'
  if (s.source === 'workspace') return `${s.provider} (workspace key)`
  if (s.source === 'server') return `${s.provider} (server key)`
  return 'Local fake provider'
}

function ProviderPlate({
  workspaceId,
  provider,
  current,
  canManage,
}: {
  workspaceId: string
  provider: (typeof providers)[number]
  current: Status['credentials'][number] | undefined
  canManage: boolean
}) {
  const qc = useQueryClient()
  const [key, setKey] = useState('')
  const [model, setModel] = useState(current?.model ?? '')
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['ai-status', workspaceId] })
  }
  const save = useMutation({
    mutationFn: async (verify: boolean) =>
      unwrap(
        await api.PUT('/api/v1/workspaces/{workspace_id}/ai/{provider}', {
          params: { path: { workspace_id: workspaceId, provider: provider.key } },
          body: { api_key: key.trim(), model: model.trim() || null, verify },
        }),
      ),
    onSuccess: (_, verify) => {
      setKey('')
      toast('Key saved', verify ? 'The provider accepted it.' : 'Saved without verification.')
      invalidate()
    },
    onError: (e) =>
      toastError('Key could not be saved', e instanceof ApiError ? e.problem.detail : undefined),
  })
  const remove = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.DELETE('/api/v1/workspaces/{workspace_id}/ai/{provider}', {
          params: { path: { workspace_id: workspaceId, provider: provider.key } },
        }),
      ),
    onSuccess: () => {
      toast('Key removed')
      invalidate()
    },
  })
  return (
    <Plate as="section" aria-label={provider.name}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-md font-semibold text-steel-100">{provider.name}</h2>
        {current ? (
          <Badge tone="strong">Configured, ends in {current.key_hint}</Badge>
        ) : (
          <Badge>Not configured</Badge>
        )}
      </div>
      <p className="mt-1 text-sm text-steel-400">{provider.purpose}</p>
      {current && (
        <p className="mt-1 text-sm text-steel-400">
          {current.verified_at
            ? `Verified ${formatDate(current.verified_at)}`
            : 'Saved without verification'}
          {current.model ? `, model ${current.model}` : ''}
        </p>
      )}
      {canManage && (
        <form
          className="mt-4 flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            if (key.trim().length >= 20) save.mutate(true)
          }}
        >
          <Input
            label={current ? 'Replace key' : 'API key'}
            type="password"
            autoComplete="off"
            placeholder={provider.placeholder}
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
          {provider.modelHint && (
            <Input
              label="Model"
              hint={provider.modelHint}
              value={model}
              onChange={(e) => setModel(e.target.value)}
              maxLength={80}
            />
          )}
          <div className="flex gap-2">
            <Button
              type="submit"
              variant="primary"
              disabled={key.trim().length < 20}
              loading={save.isPending}
              loadingLabel="Verifying..."
            >
              Verify and save key
            </Button>
            <Button
              variant="ghost"
              disabled={key.trim().length < 20}
              onClick={() => save.mutate(false)}
              loading={save.isPending}
              loadingLabel="Saving..."
            >
              Save without verifying
            </Button>
            {current && (
              <Button
                variant="ghost"
                onClick={() => remove.mutate()}
                loading={remove.isPending}
                loadingLabel="Removing..."
              >
                Remove key
              </Button>
            )}
          </div>
        </form>
      )}
    </Plate>
  )
}

export function AISettings() {
  const { workspace } = useActiveWorkspace()
  const id = workspace?.workspace_id ?? null
  const { data } = useAIStatus(id)
  if (!id || !data) return <p className="text-sm text-steel-400">Loading</p>
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1 text-sm">
        <p className="text-steel-300">
          Extraction and summaries: <span className="text-steel-100">{sourceLabel(data.llm)}</span>
        </p>
        <p className="text-steel-300">
          Transcription: <span className="text-steel-100">{sourceLabel(data.transcription)}</span>
        </p>
        <p className="mt-2 text-steel-400">
          Keys are stored encrypted for this workspace and used only by its background jobs. Usage
          is billed to your provider account. The workspace token budget still applies.
        </p>
      </div>
      {!data.can_manage && (
        <p className="text-sm text-steel-400">Only admins can add or change keys.</p>
      )}
      {providers.map((p) => (
        <ProviderPlate
          key={p.key}
          workspaceId={id}
          provider={p}
          current={data.credentials.find((c) => c.provider === p.key)}
          canManage={data.can_manage}
        />
      ))}
    </div>
  )
}
