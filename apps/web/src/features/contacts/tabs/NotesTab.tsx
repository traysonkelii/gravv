import { useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input, Select } from '@/components/ui/Field'
import { ListSkeleton } from '@/components/ui/Skeleton'
import { toast, toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import { formatDate } from '@/lib/format'
import {
  useCreateFact,
  useDeleteFact,
  useFacts,
  useUpdateFact,
  type Contact,
  type Fact,
} from '@/features/contacts/api'

const categories: { key: Fact['category']; label: string }[] = [
  { key: 'preference', label: 'Preferences' },
  { key: 'dislike', label: 'Dislikes' },
  { key: 'interest', label: 'Interests' },
  { key: 'personal', label: 'Personal' },
  { key: 'family', label: 'Family' },
  { key: 'professional', label: 'Professional' },
  { key: 'communication_style', label: 'Communication style' },
  { key: 'ambition', label: 'Ambitions' },
  { key: 'risk', label: 'Risks' },
  { key: 'other', label: 'Other' },
]

function FactRow({
  fact,
  contactId,
  editable,
}: {
  fact: Fact
  contactId: string
  editable: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [content, setContent] = useState(fact.content)
  const update = useUpdateFact(contactId)
  const remove = useDeleteFact(contactId)
  const save = async () => {
    if (!content.trim() || content.trim() === fact.content) return setEditing(false)
    try {
      await update.mutateAsync({ id: fact.id, content: content.trim() })
      toast('Note updated')
      setEditing(false)
    } catch (e) {
      toastError('Note could not be updated', e instanceof ApiError ? e.problem.detail : undefined)
    }
  }
  return (
    <li className="flex flex-col gap-1 border-b border-steel-600 py-3">
      {editing ? (
        <div className="flex items-end gap-2">
          <Input
            label="Edit note"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            maxLength={500}
            className="flex-1"
          />
          <Button variant="primary" onClick={save} loading={update.isPending}>
            Save note
          </Button>
          <Button variant="ghost" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span
            className={`text-base ${fact.is_active ? 'text-steel-100' : 'text-steel-500 line-through'}`}
          >
            {fact.content}
          </span>
          <Badge tone={fact.category === 'risk' ? 'risk' : 'status'}>{fact.source}</Badge>
          <span className="text-sm text-steel-400">since {formatDate(fact.created_at)}</span>
          {editable && fact.is_active && (
            <span className="ml-auto flex gap-1">
              <Button variant="ghost" onClick={() => setEditing(true)}>
                Edit
              </Button>
              <Button
                variant="ghost"
                onClick={() => remove.mutate(fact.id, { onSuccess: () => toast('Note archived') })}
              >
                Archive
              </Button>
            </span>
          )}
        </div>
      )}
    </li>
  )
}

export function NotesTab({ contact }: { contact: Contact }) {
  const [showArchived, setShowArchived] = useState(false)
  const { data, isLoading } = useFacts(contact.id, showArchived)
  const create = useCreateFact(contact.id)
  const [draft, setDraft] = useState<{ category: Fact['category']; content: string }>({
    category: 'preference',
    content: '',
  })
  const facts = data ?? []
  return (
    <div className="flex flex-col gap-6">
      <form
        className="flex flex-col gap-2 md:flex-row md:items-end"
        onSubmit={async (e) => {
          e.preventDefault()
          if (!draft.content.trim()) return
          try {
            await create.mutateAsync({
              category: draft.category,
              content: draft.content.trim(),
              source: 'manual',
            })
            toast('Saved to remember')
            setDraft({ ...draft, content: '' })
          } catch (err) {
            toastError(
              'Note could not be added',
              err instanceof ApiError ? err.problem.detail : undefined,
            )
          }
        }}
      >
        <Select
          label="Category"
          value={draft.category}
          onChange={(e) => setDraft({ ...draft, category: e.target.value as Fact['category'] })}
          className="md:w-52"
        >
          {categories.map((c) => (
            <option key={c.key} value={c.key}>
              {c.label}
            </option>
          ))}
        </Select>
        <Input
          label="Something to remember"
          placeholder="Drinks Diet Coke, never coffee"
          value={draft.content}
          onChange={(e) => setDraft({ ...draft, content: e.target.value })}
          maxLength={500}
          className="flex-1"
        />
        <Button
          type="submit"
          variant="primary"
          loading={create.isPending}
          disabled={!draft.content.trim()}
        >
          Remember this
        </Button>
      </form>
      {isLoading ? (
        <ListSkeleton rows={3} />
      ) : facts.length === 0 ? (
        <p className="text-base text-steel-300">
          Nothing recorded yet. Add the small things that make the next conversation easier.
        </p>
      ) : (
        categories
          .filter((c) => facts.some((f) => f.category === c.key))
          .map((c) => (
            <section key={c.key}>
              <h2 className="text-md font-semibold text-steel-100">{c.label}</h2>
              <ul>
                {facts
                  .filter((f) => f.category === c.key)
                  .map((f) => (
                    <FactRow key={f.id} fact={f} contactId={contact.id} editable />
                  ))}
              </ul>
            </section>
          ))
      )}
      <div>
        <Button variant="ghost" onClick={() => setShowArchived((s) => !s)}>
          {showArchived ? 'Hide archived' : 'Show archived'}
        </Button>
      </div>
    </div>
  )
}
