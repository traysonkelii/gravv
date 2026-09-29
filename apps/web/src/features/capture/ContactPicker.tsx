import { useEffect, useState } from 'react'
import { Avatar } from '@/components/ui/Avatar'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Field'
import { useContacts, type Contact } from '@/features/contacts/api'

type Props = { value: Contact | null; onChange: (c: Contact | null) => void; label?: string }

export function ContactPicker({ value, onChange, label = 'Contact' }: Props) {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 200)
    return () => clearTimeout(t)
  }, [q])
  const results = useContacts({ q: debounced || undefined, sort: 'last_interaction' })
  const items = (results.data?.pages.flatMap((p) => p.items) ?? []).slice(0, 6)
  if (value) {
    return (
      <div className="flex items-center gap-3 border border-steel-600 px-3 py-2">
        <Avatar name={value.display_name} band={value.band} size={32} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-base text-steel-100">
            {value.honorific ? `${value.honorific} ` : ''}
            {value.display_name}
          </p>
          <p className="truncate text-sm text-steel-400">
            {[value.company?.name, value.title].filter(Boolean).join(', ')}
          </p>
        </div>
        <Button variant="ghost" onClick={() => onChange(null)}>
          Change
        </Button>
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-2">
      <Input
        label={label}
        placeholder="Search by name"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        autoComplete="off"
      />
      {items.length > 0 && (
        <ul
          className="max-h-60 overflow-y-auto border border-steel-600"
          role="listbox"
          aria-label="Matching contacts"
        >
          {items.map((c) => (
            <li key={c.id} role="option" aria-selected={false}>
              <button
                type="button"
                onClick={() => onChange(c)}
                className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-steel-700"
              >
                <Avatar name={c.display_name} band={c.band} size={32} />
                <span className="min-w-0">
                  <span className="block truncate text-base text-steel-100">{c.display_name}</span>
                  <span className="block truncate text-sm text-steel-400">
                    {[c.company?.name, c.title].filter(Boolean).join(', ')}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
