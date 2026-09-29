import { Badge } from '@/components/ui/Badge'
import { copy } from '@/lib/copy'
import { compactCurrency, dueLabel, relativeTime } from '@/lib/format'
import type { Contact } from '@/features/contacts/api'

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-steel-600 py-3 md:grid-cols-4">
      <dt className="text-sm text-steel-400">{label}</dt>
      <dd className="text-base text-steel-200 md:col-span-3">{children}</dd>
    </div>
  )
}

export function OverviewTab({ contact }: { contact: Contact }) {
  const p = contact.profile
  const last = contact.last_interaction
  return (
    <dl>
      <Row label="Summary">
        {p?.summary ? (
          <>
            <p className="max-w-prose">{p.summary}</p>
            <p className="mt-1 text-sm text-steel-400">
              Updated {relativeTime(p.generated_at)}
              {p.stale ? ', new notes since' : ''}
            </p>
          </>
        ) : (
          <span className="text-steel-400">
            No summary yet. It is written once there are notes to summarize.
          </span>
        )}
      </Row>
      <Row label={copy.style}>
        {p?.communication_style ?? <span className="text-steel-400">Not recorded</span>}
      </Row>
      <Row label="Remember">
        {p?.remember.length ? (
          p.remember.join('; ')
        ) : (
          <span className="text-steel-400">Add notes to remember in the Notes tab.</span>
        )}
      </Row>
      <Row label="Last interaction">
        {last ? (
          `${last.kind}, ${relativeTime(last.occurred_at)}`
        ) : (
          <span className="text-steel-400">None yet</span>
        )}
      </Row>
      <Row label="Next due">
        {contact.next_due_at
          ? dueLabel(contact.next_due_at)
          : `${contact.cadence_days}-day ${copy.orbit}`}
      </Row>
      <Row label="Open deals">
        {contact.open_opportunity_value_cents > 0 ? (
          compactCurrency(contact.open_opportunity_value_cents)
        ) : (
          <span className="text-steel-400">None</span>
        )}
      </Row>
      <Row label="Risks">
        {p?.risks.length ? (
          <ul className="flex flex-wrap gap-2">
            {p.risks.map((r) => (
              <li key={r}>
                <Badge tone="risk">{r}</Badge>
              </li>
            ))}
          </ul>
        ) : (
          <span className="text-steel-400">None recorded</span>
        )}
      </Row>
      <Row label="Common ground with you">
        {p?.common_ground.length ? (
          p.common_ground.join('; ')
        ) : (
          <span className="text-steel-400">None yet</span>
        )}
      </Row>
      <Row label="Details">
        <div className="flex flex-col gap-1 text-sm">
          {contact.emails.map((e) => (
            <a key={e} href={`mailto:${e}`} className="text-steel-200 hover:text-steel-050">
              {e}
            </a>
          ))}
          {contact.phones.map((ph) => (
            <a key={ph} href={`tel:${ph}`} className="tnum text-steel-200 hover:text-steel-050">
              {ph}
            </a>
          ))}
          {contact.location && <span className="text-steel-300">{contact.location}</span>}
          <span className="text-steel-400">
            {contact.relationship_type},{' '}
            {contact.visibility === 'private' ? 'private' : 'visible to team'}
            {contact.tags.length ? `, tags: ${contact.tags.join(', ')}` : ''}
          </span>
        </div>
      </Row>
    </dl>
  )
}
