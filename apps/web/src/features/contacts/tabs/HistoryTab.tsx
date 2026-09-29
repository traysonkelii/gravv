import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Chip } from '@/components/ui/Chip'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input, Select, Textarea } from '@/components/ui/Field'
import { Sheet } from '@/components/ui/Sheet'
import { ListSkeleton } from '@/components/ui/Skeleton'
import { Timeline, type TimelineItem } from '@/components/ui/Timeline'
import { toast, toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import { useMe } from '@/lib/api/me'
import type { Band } from '@/lib/copy'
import {
  useCreateInteraction,
  useDeleteInteraction,
  useTimeline,
  type Contact,
} from '@/features/contacts/api'

const kinds = [
  'note',
  'meeting',
  'call',
  'email',
  'message',
  'event',
  'introduction',
  'gift',
] as const
const filterKinds = [...kinds, 'task', 'score'] as const

const schema = z.object({
  kind: z.enum(kinds),
  direction: z.enum(['inbound', 'outbound', 'mutual']),
  occurred_at: z.string().min(1, 'Pick a date and time'),
  subject: z.string().max(200),
  body: z.string().min(1, 'Write what happened').max(20000),
  sentiment: z.enum(['', 'positive', 'neutral', 'negative', 'mixed']),
})
type Form = z.infer<typeof schema>

function localNow(): string {
  const d = new Date()
  d.setSeconds(0, 0)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function AddInteraction({
  contact,
  open,
  onClose,
}: {
  contact: Contact
  open: boolean
  onClose: () => void
}) {
  const create = useCreateInteraction(contact.id)
  const { register, handleSubmit, formState, reset } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: {
      kind: 'note',
      direction: 'mutual',
      occurred_at: localNow(),
      subject: '',
      body: '',
      sentiment: '',
    },
  })
  return (
    <Sheet open={open} title={`Add note for ${contact.display_name}`} onClose={onClose}>
      <form
        className="flex flex-col gap-4"
        noValidate
        onSubmit={handleSubmit(async (v) => {
          try {
            await create.mutateAsync({
              contact_id: contact.id,
              kind: v.kind,
              direction: v.direction,
              occurred_at: new Date(v.occurred_at).toISOString(),
              subject: v.subject || null,
              body: v.body,
              sentiment: v.sentiment || null,
            })
            toast('Note saved')
            reset({
              kind: 'note',
              direction: 'mutual',
              occurred_at: localNow(),
              subject: '',
              body: '',
              sentiment: '',
            })
            onClose()
          } catch (e) {
            toastError(
              'Note could not be saved',
              e instanceof ApiError ? e.problem.detail : undefined,
            )
          }
        })}
      >
        <div className="grid grid-cols-2 gap-3">
          <Select label="Kind" {...register('kind')}>
            {kinds.map((k) => (
              <option key={k} value={k}>
                {k[0]!.toUpperCase() + k.slice(1)}
              </option>
            ))}
          </Select>
          <Select label="Direction" {...register('direction')}>
            <option value="mutual">Both ways</option>
            <option value="outbound">I reached out</option>
            <option value="inbound">They reached out</option>
          </Select>
        </div>
        <Input
          label="When"
          type="datetime-local"
          {...register('occurred_at')}
          error={formState.errors.occurred_at?.message}
        />
        <Input label="Subject" {...register('subject')} />
        <Textarea
          label="What happened"
          rows={6}
          {...register('body')}
          error={formState.errors.body?.message}
        />
        <Select label="Tone" {...register('sentiment')}>
          <option value="">Not sure</option>
          <option value="positive">Positive</option>
          <option value="neutral">Neutral</option>
          <option value="mixed">Mixed</option>
          <option value="negative">Negative</option>
        </Select>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={create.isPending}>
            Save note
          </Button>
        </div>
      </form>
    </Sheet>
  )
}

export function HistoryTab({ contact }: { contact: Contact }) {
  const [kind, setKind] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const { data: me } = useMe()
  const query = useTimeline(contact.id, kind ? [kind] : undefined)
  const remove = useDeleteInteraction(contact.id)
  const entries = query.data?.pages.flatMap((p) => p.items) ?? []
  const items: TimelineItem[] = entries.map((e) => ({
    id: e.id,
    ts: e.ts,
    kind: e.kind,
    title: e.title,
    body: e.body,
    band: (e.meta as { band?: Band }).band,
    actions:
      e.entry_type === 'interaction' &&
      (e.meta as { user_id?: string }).user_id === me?.profile.id ? (
        <Button variant="ghost" onClick={() => remove.mutate(e.id)}>
          Delete
        </Button>
      ) : undefined,
  }))
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-2" aria-label="Filter by kind">
          {filterKinds.map((k) => (
            <Chip
              key={k}
              label={k[0]!.toUpperCase() + k.slice(1)}
              selected={kind === k}
              onClick={() => setKind(kind === k ? null : k)}
            />
          ))}
        </div>
        <Button variant="primary" className="ml-auto" onClick={() => setAdding(true)}>
          Add note
        </Button>
      </div>
      <div className="mt-6">
        {query.isLoading ? (
          <ListSkeleton />
        ) : items.length === 0 ? (
          <EmptyState
            title="No history yet"
            body="Log a meeting, call, or note to start the timeline."
            action={
              <Button variant="primary" onClick={() => setAdding(true)}>
                Add note
              </Button>
            }
          />
        ) : (
          <>
            <Timeline items={items} timeZone={me?.profile.timezone} />
            {query.hasNextPage && (
              <div className="mt-4">
                <Button
                  onClick={() => query.fetchNextPage()}
                  loading={query.isFetchingNextPage}
                  loadingLabel="Loading..."
                >
                  Load more
                </Button>
              </div>
            )}
          </>
        )}
      </div>
      <AddInteraction contact={contact} open={adding} onClose={() => setAdding(false)} />
    </div>
  )
}
