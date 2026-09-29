import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Checkbox } from '@/components/ui/Checkbox'
import { Input, Select } from '@/components/ui/Field'
import { toast, toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import { useActiveWorkspace, useSwitchWorkspace } from '@/lib/workspace'
import {
  useCreateWorkspace,
  useUpdateWorkspace,
  useWorkspace,
  type Workspace,
} from '@/features/settings/api'

const schema = z.object({
  name: z.string().min(1, 'Enter a name').max(120),
  slug: z
    .string()
    .max(40)
    .regex(/^$|^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])?$/, 'Lowercase letters, numbers, and hyphens'),
  default_contact_visibility: z.enum(['team', 'private']),
  default_cadence_days: z.number().int().min(1).max(365),
  auto_apply_low_risk_facts: z.boolean(),
  require_mfa: z.boolean(),
  retain_audio: z.boolean(),
})
type Form = z.infer<typeof schema>

function CreateOrganization() {
  const create = useCreateWorkspace()
  const switchTo = useSwitchWorkspace()
  const [name, setName] = useState('')
  return (
    <div className="mt-8 border-t border-steel-600 pt-6">
      <h2 className="text-md font-semibold text-steel-100">Create an organization</h2>
      <p className="mt-1 text-sm text-steel-400">You become its owner and can invite teammates.</p>
      <div className="mt-3 flex items-end gap-2">
        <Input
          label="Organization name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="flex-1"
          maxLength={120}
        />
        <Button
          variant="primary"
          disabled={!name.trim()}
          loading={create.isPending}
          onClick={async () => {
            try {
              const ws = await create.mutateAsync({ name: name.trim() })
              switchTo(ws.id)
              setName('')
              toast('Organization created')
            } catch (e) {
              toastError(
                'Organization could not be created',
                e instanceof ApiError ? e.problem.detail : undefined,
              )
            }
          }}
        >
          Create organization
        </Button>
      </div>
    </div>
  )
}

export function WorkspaceSettings() {
  const { workspace } = useActiveWorkspace()
  const id = workspace?.workspace_id ?? null
  const { data: ws } = useWorkspace(id)
  if (!ws) return <p className="text-sm text-steel-400">Loading</p>
  return <WorkspaceForm key={ws.id} ws={ws} />
}

function WorkspaceForm({ ws }: { ws: Workspace }) {
  const update = useUpdateWorkspace(ws.id)
  const isAdmin = ws.my_role === 'admin' || ws.my_role === 'owner'
  const s = ws.settings as Record<string, unknown>
  const { register, handleSubmit, formState } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: ws.name,
      slug: ws.slug ?? '',
      default_contact_visibility: (s.default_contact_visibility as 'team' | 'private') ?? 'team',
      default_cadence_days: (s.default_cadence_days as number) ?? 30,
      auto_apply_low_risk_facts: !!s.auto_apply_low_risk_facts,
      require_mfa: !!s.require_mfa,
      retain_audio: !!s.retain_audio,
    },
  })
  const personal = ws.kind === 'personal'
  return (
    <div>
      <form
        className="flex flex-col gap-4"
        noValidate
        onSubmit={handleSubmit(async (v) => {
          try {
            await update.mutateAsync({
              name: v.name,
              ...(personal ? {} : { slug: v.slug || null }),
              settings: {
                default_contact_visibility: v.default_contact_visibility,
                default_cadence_days: v.default_cadence_days,
                auto_apply_low_risk_facts: v.auto_apply_low_risk_facts,
                require_mfa: v.require_mfa,
                retain_audio: v.retain_audio,
              },
            })
            toast('Workspace saved')
          } catch (e) {
            toastError(
              'Workspace could not be saved',
              e instanceof ApiError ? e.problem.detail : undefined,
            )
          }
        })}
      >
        <fieldset disabled={!isAdmin} className="flex flex-col gap-4">
          <Input label="Name" {...register('name')} error={formState.errors.name?.message} />
          {!personal && (
            <Input
              label="Slug"
              hint="Short handle, for example meridian."
              {...register('slug')}
              error={formState.errors.slug?.message}
            />
          )}
          <Select label="Default contact visibility" {...register('default_contact_visibility')}>
            <option value="team">Team</option>
            <option value="private">Private</option>
          </Select>
          <Input
            label="Default cadence in days"
            type="number"
            min={1}
            max={365}
            {...register('default_cadence_days', { valueAsNumber: true })}
            error={formState.errors.default_cadence_days?.message}
          />
          <Checkbox
            label="Apply low-risk facts automatically"
            description="Preferences, interests, and dislikes with high confidence are added without review. One-tap undo."
            {...register('auto_apply_low_risk_facts')}
          />
          {!personal && (
            <Checkbox
              label="Require multi-factor authentication for managers and above"
              {...register('require_mfa')}
            />
          )}
          <Checkbox
            label="Keep voice recordings"
            description="Otherwise audio is deleted 30 days after a note is confirmed."
            {...register('retain_audio')}
          />
        </fieldset>
        {isAdmin ? (
          <div className="flex justify-end">
            <Button type="submit" variant="primary" loading={update.isPending}>
              Save workspace
            </Button>
          </div>
        ) : (
          <p className="text-sm text-steel-400">
            Only admins and the owner can change these settings.
          </p>
        )}
      </form>
      <CreateOrganization />
    </div>
  )
}
