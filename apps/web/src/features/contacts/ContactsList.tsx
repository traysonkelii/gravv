import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { Avatar } from '@/components/ui/Avatar'
import { Button } from '@/components/ui/Button'
import { Chip } from '@/components/ui/Chip'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input, Select } from '@/components/ui/Field'
import { ScoreBlade } from '@/components/ui/ScoreBlade'
import { ListSkeleton } from '@/components/ui/Skeleton'
import { copy } from '@/lib/copy'
import { dueLabel, relativeTime } from '@/lib/format'
import { useUiStore } from '@/lib/store'
import { useContacts, type Contact, type ContactFilters } from '@/features/contacts/api'

const bands = ['strong', 'steady', 'weak', 'drifting'] as const
const statuses = ['active', 'follow_up', 'needs_attention', 'drifting', 'archived'] as const
const relTypes = ['client', 'partner', 'vendor', 'colleague', 'government', 'other'] as const

export function ContactRow({ contact }: { contact: Contact }) {
  const meta = [contact.company?.name, contact.title].filter(Boolean).join(', ')
  const due = contact.next_due_at ? dueLabel(contact.next_due_at) : null
  return (
    <li>
      <Link
        to={`/app/contacts/${contact.id}`}
        className="flex min-h-14 items-center gap-3 border-b border-steel-600 px-2 py-2 hover:bg-steel-700"
      >
        <Avatar name={contact.display_name} band={contact.band} size={40} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-base text-steel-100">
            {contact.honorific ? `${contact.honorific} ` : ''}
            {contact.display_name}
          </p>
          <p className="truncate text-sm text-steel-400">{meta || 'No company'}</p>
        </div>
        <div className="hidden w-48 shrink-0 sm:block">
          <ScoreBlade score={contact.gravity_score} band={contact.band} />
        </div>
        <div className="w-24 shrink-0 text-right text-sm text-steel-400 sm:w-32">
          <span className="tnum text-steel-100 sm:hidden">{contact.gravity_score}</span>
          <span className="hidden sm:inline">
            {due ?? relativeTime(contact.last_interaction?.occurred_at)}
          </span>
        </div>
      </Link>
    </li>
  )
}

export function ContactsList() {
  const navigate = useNavigate()
  const openCapture = useUiStore((s) => s.openCapture)
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [filters, setFilters] = useState<ContactFilters>({ sort: 'updated' })
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 250)
    return () => clearTimeout(t)
  }, [q])
  const query = useContacts({ ...filters, q: debounced || undefined })
  const items = query.data?.pages.flatMap((p) => p.items) ?? []
  const toggle = <K extends keyof ContactFilters>(key: K, value: ContactFilters[K]) =>
    setFilters((f) => ({ ...f, [key]: f[key] === value ? undefined : value }))

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <h1 className="font-display text-2xl font-bold text-steel-100">{copy.contacts}</h1>
        <Button variant="primary" onClick={() => navigate('/app/contacts/new')}>
          Add contact
        </Button>
      </div>
      <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-end">
        <Input
          label="Search contacts"
          placeholder="Name, title, tag, or company"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="md:flex-1"
        />
        <Select
          label="Sort"
          value={filters.sort}
          onChange={(e) =>
            setFilters({ ...filters, sort: e.target.value as ContactFilters['sort'] })
          }
          className="md:w-48"
        >
          <option value="updated">Recently updated</option>
          <option value="gravity">{copy.gravity}</option>
          <option value="last_interaction">Last interaction</option>
          <option value="name">Name</option>
          <option value="next_due">Next due</option>
        </Select>
      </div>
      <div className="mt-3 flex flex-wrap gap-2" aria-label="Filters">
        <Chip
          label="Mine"
          selected={filters.owner === 'me'}
          onClick={() => toggle('owner', 'me')}
        />
        {bands.map((b) => (
          <Chip
            key={b}
            label={copy.band[b]}
            selected={filters.band === b}
            onClick={() => toggle('band', b)}
          />
        ))}
        {statuses.map((s) => (
          <Chip
            key={s}
            label={copy.status[s]}
            selected={filters.status === s}
            onClick={() => toggle('status', s)}
          />
        ))}
        {relTypes.map((r) => (
          <Chip
            key={r}
            label={r[0]!.toUpperCase() + r.slice(1)}
            selected={filters.relationship_type === r}
            onClick={() => toggle('relationship_type', r)}
          />
        ))}
      </div>
      <div className="mt-4">
        {query.isLoading ? (
          <ListSkeleton />
        ) : items.length === 0 ? (
          <EmptyState
            title="No contacts yet"
            body="Add one or capture a note about someone."
            action={
              <div className="flex gap-2">
                <Button variant="primary" onClick={() => navigate('/app/contacts/new')}>
                  Add contact
                </Button>
                <Button onClick={() => openCapture()}>Capture a note</Button>
              </div>
            }
          />
        ) : (
          <>
            <ul className="border-t border-steel-600">
              {items.map((c) => (
                <ContactRow key={c.id} contact={c} />
              ))}
            </ul>
            {query.hasNextPage && (
              <div className="mt-4 flex justify-center">
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
    </div>
  )
}
