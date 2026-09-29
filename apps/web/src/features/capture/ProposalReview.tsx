import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Button } from '@/components/ui/Button'
import { Checkbox } from '@/components/ui/Checkbox'
import { Input, Select, Textarea } from '@/components/ui/Field'
import { Plate } from '@/components/ui/Plate'
import { Skeleton } from '@/components/ui/Skeleton'
import { toast, toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import { formatDateTime } from '@/lib/format'
import { ContactPicker } from '@/features/capture/ContactPicker'
import {
  useCapture,
  useConfirmCapture,
  useDiscardCapture,
  type Capture,
  type Extraction,
} from '@/features/capture/api'
import { useContact, useFacts, type Contact } from '@/features/contacts/api'

type FactRow = NonNullable<Extraction['facts']>[number] & { on: boolean }

const kinds = [
  'note',
  'meeting',
  'call',
  'email',
  'message',
  'event',
  'introduction',
  'gift',
  'other',
] as const

function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function Editor({ capture, extraction }: { capture: Capture; extraction: Extraction }) {
  const navigate = useNavigate()
  const matchedId = extraction.contact_match?.contact_id ?? capture.contact_id ?? undefined
  const { data: matched } = useContact(matchedId)
  const [picked, setPicked] = useState<Contact | null>(null)
  const contact = picked ?? matched ?? null
  const { data: existing } = useFacts(contact?.id, false)
  const confirm = useConfirmCapture(capture.id)
  const discard = useDiscardCapture(capture.id)

  const [interaction, setInteraction] = useState({
    kind: extraction.interaction.kind,
    occurred_at: toLocalInput(extraction.interaction.occurred_at ?? new Date().toISOString()),
    subject: extraction.interaction.subject ?? '',
    summary: extraction.interaction.summary ?? '',
    body: extraction.interaction.body ?? '',
  })
  const [facts, setFacts] = useState<FactRow[]>(() =>
    (extraction.facts ?? []).map((f) => ({ ...f, on: true })),
  )
  const [tasks, setTasks] = useState(() =>
    (extraction.tasks ?? []).map((t) => ({ ...t, on: true, due: toLocalInput(t.due_at) })),
  )
  const [people, setPeople] = useState(() =>
    (extraction.mentioned_people ?? []).map((p) => ({ ...p, on: false })),
  )
  const autoApplied = new Set(
    (capture.provenance as { auto_applied_fact_ids?: string[] }).auto_applied_fact_ids ?? [],
  )

  const known = new Set((existing ?? []).map((f) => f.content.trim().toLowerCase()))
  const already = (f: FactRow) => known.has(f.content.trim().toLowerCase())

  const save = async () => {
    if (!contact) return toastError('Pick a contact first')
    try {
      const result = await confirm.mutateAsync({
        contact_id: contact.id,
        interaction: {
          ...extraction.interaction,
          kind: interaction.kind,
          occurred_at: interaction.occurred_at
            ? new Date(interaction.occurred_at).toISOString()
            : null,
          subject: interaction.subject,
          summary: interaction.summary,
          body: interaction.body,
        },
        facts: facts.filter((f) => f.on && !already(f)).map(({ on: _on, ...f }) => f),
        tasks: tasks
          .filter((t) => t.on)
          .map(({ on: _on, due, ...t }) => ({
            ...t,
            due_at: due ? new Date(due).toISOString() : null,
          })),
        edges: extraction.edges ?? [],
        create_contacts_for: people.filter((p) => p.on).map(({ on: _on, ...p }) => p),
      })
      toast(`Saved to ${result.contact.display_name}`)
      navigate(`/app/contacts/${result.contact.id}`, { replace: true })
    } catch (e) {
      toastError('Note could not be saved', e instanceof ApiError ? e.problem.detail : undefined)
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-8">
      <details className="border border-steel-600 p-4">
        <summary className="cursor-pointer text-sm text-steel-300">Transcript</summary>
        <p className="mt-2 whitespace-pre-wrap text-base text-steel-200">
          {capture.transcript ?? capture.raw_text}
        </p>
      </details>

      <section className="flex flex-col gap-2">
        <h2 className="text-md font-semibold text-steel-100">Contact</h2>
        <ContactPicker value={contact} onChange={setPicked} label="Who is this about" />
        {extraction.contact_match && !picked && (
          <p className="text-sm text-steel-400">
            Matched with {Math.round(extraction.contact_match.confidence * 100)}% confidence.
          </p>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-md font-semibold text-steel-100">Interaction</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <Select
            label="Kind"
            value={interaction.kind}
            onChange={(e) =>
              setInteraction({ ...interaction, kind: e.target.value as typeof interaction.kind })
            }
          >
            {kinds.map((k) => (
              <option key={k} value={k}>
                {k[0]!.toUpperCase() + k.slice(1)}
              </option>
            ))}
          </Select>
          <Input
            label="When"
            type="datetime-local"
            value={interaction.occurred_at}
            onChange={(e) => setInteraction({ ...interaction, occurred_at: e.target.value })}
          />
        </div>
        <Input
          label="Subject"
          value={interaction.subject}
          onChange={(e) => setInteraction({ ...interaction, subject: e.target.value })}
          maxLength={200}
        />
        <Textarea
          label="Summary"
          rows={2}
          value={interaction.summary}
          onChange={(e) => setInteraction({ ...interaction, summary: e.target.value })}
          maxLength={500}
        />
        <Textarea
          label="Note"
          rows={5}
          value={interaction.body}
          onChange={(e) => setInteraction({ ...interaction, body: e.target.value })}
        />
      </section>

      <section className="flex flex-col gap-1">
        <h2 className="text-md font-semibold text-steel-100">Facts to remember</h2>
        {facts.length === 0 && (
          <p className="text-sm text-steel-400">Nothing new to remember from this note.</p>
        )}
        {facts.map((f, i) => (
          <Checkbox
            key={`${f.content}-${i}`}
            label={f.content}
            description={`${f.category.replace('_', ' ')}${already(f) ? ', already recorded' : ''}${f.supersedes ? `, replaces: ${f.supersedes}` : ''}`}
            checked={f.on}
            onChange={(e) =>
              setFacts(facts.map((x, j) => (j === i ? { ...x, on: e.target.checked } : x)))
            }
          />
        ))}
        {autoApplied.size > 0 && (
          <p className="text-sm text-steel-400">
            {autoApplied.size} low-risk fact(s) were added automatically; archive them from the
            Notes tab to undo.
          </p>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-md font-semibold text-steel-100">Tasks</h2>
        {tasks.length === 0 && <p className="text-sm text-steel-400">No follow-ups found.</p>}
        {tasks.map((t, i) => (
          <div
            key={i}
            className="flex flex-col gap-2 border-b border-steel-600 pb-3 md:flex-row md:items-end"
          >
            <Checkbox
              label=""
              aria-label={`Include task ${t.title}`}
              checked={t.on}
              onChange={(e) =>
                setTasks(tasks.map((x, j) => (j === i ? { ...x, on: e.target.checked } : x)))
              }
              className="md:pb-3"
            />
            <Input
              label="Task"
              value={t.title}
              onChange={(e) =>
                setTasks(tasks.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))
              }
              className="flex-1"
              maxLength={200}
            />
            <Input
              label="Due"
              type="datetime-local"
              value={t.due}
              onChange={(e) =>
                setTasks(tasks.map((x, j) => (j === i ? { ...x, due: e.target.value } : x)))
              }
              className="md:w-60"
            />
          </div>
        ))}
      </section>

      {people.length > 0 && (
        <section className="flex flex-col gap-1">
          <h2 className="text-md font-semibold text-steel-100">New people mentioned</h2>
          {people.map((p, i) => (
            <Checkbox
              key={p.name}
              label={`Add ${p.name}${p.title ? `, ${p.title}` : ''}${p.company ? ` (${p.company})` : ''} as a contact`}
              checked={p.on}
              onChange={(e) =>
                setPeople(people.map((x, j) => (j === i ? { ...x, on: e.target.checked } : x)))
              }
            />
          ))}
        </section>
      )}

      {(extraction.needs_review ?? []).length > 0 && (
        <Plate>
          <h2 className="text-md font-semibold text-steel-100">Model notes</h2>
          <ul className="mt-2 flex flex-col gap-1 text-sm text-steel-300">
            {(extraction.needs_review ?? []).map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </Plate>
      )}

      <div className="flex justify-between">
        <Button
          variant="ghost"
          loading={discard.isPending}
          loadingLabel="Discarding..."
          onClick={async () => {
            await discard.mutateAsync()
            toast('Capture discarded')
            navigate('/app/home', { replace: true })
          }}
        >
          Discard
        </Button>
        <Button variant="primary" loading={confirm.isPending} onClick={save} disabled={!contact}>
          {contact ? `Save to ${contact.display_name}` : 'Save note'}
        </Button>
      </div>
    </div>
  )
}

export function ProposalReview() {
  const { id } = useParams()
  const { data: capture, isLoading, isError } = useCapture(id)
  if (isLoading || !capture) {
    if (isError) return <p className="text-base text-rust-400">This capture could not be loaded.</p>
    return <Skeleton className="h-64 w-full" />
  }
  const pendingLabel: Record<string, string> = {
    uploaded: 'Waiting for the recording',
    transcribing: 'Transcribing',
    transcribed: 'Transcribed, extracting',
    extracting: 'Extracting facts and follow-ups',
  }
  if (capture.status in pendingLabel) {
    return (
      <div className="flex flex-col gap-4" aria-busy>
        <h1 className="font-display text-2xl font-bold text-steel-100">
          {pendingLabel[capture.status]}
        </h1>
        <p className="text-sm text-steel-400">
          Started {formatDateTime(capture.created_at)}. This usually takes a few seconds.
        </p>
        <Skeleton className="h-40 w-full max-w-2xl" />
      </div>
    )
  }
  if (capture.status === 'failed') {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="font-display text-2xl font-bold text-steel-100">
          Capture could not be processed
        </h1>
        <p className="text-base text-steel-300">{capture.error ?? 'Something went wrong.'}</p>
        <p className="text-sm text-steel-400">The text is kept below so nothing is lost.</p>
        <p className="whitespace-pre-wrap border border-steel-600 p-4 text-base text-steel-200">
          {capture.transcript ?? capture.raw_text}
        </p>
        <Link to="/app/home" className="text-steel-200 hover:text-steel-050">
          Back to home
        </Link>
      </div>
    )
  }
  if (capture.status === 'confirmed' || capture.status === 'discarded') {
    return (
      <div className="flex flex-col gap-3">
        <h1 className="font-display text-2xl font-bold text-steel-100">
          {capture.status === 'confirmed' ? 'Already saved' : 'Discarded'}
        </h1>
        {capture.contact_id && (
          <Link
            to={`/app/contacts/${capture.contact_id}`}
            className="text-steel-200 hover:text-steel-050"
          >
            Open the contact
          </Link>
        )}
      </div>
    )
  }
  if (!capture.proposal)
    return <p className="text-base text-steel-300">No proposal was produced.</p>
  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-steel-100">Review capture</h1>
      <p className="mt-1 text-sm text-steel-400">
        Everything below is a proposal. Edit, untick, then save.
      </p>
      <div className="mt-6">
        <Editor capture={capture} extraction={capture.proposal} />
      </div>
    </div>
  )
}
