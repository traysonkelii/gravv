import { Link } from 'react-router'
import { Badge } from '@/components/ui/Badge'
import { compactCurrency, formatDate } from '@/lib/format'
import type { Contact } from '@/features/contacts/api'
import { useOpportunities } from '@/features/deals/api'

export function DealsTab({ contact }: { contact: Contact }) {
  const list = useOpportunities({})
  const deals = (list.data?.pages.flatMap((p) => p.items) ?? []).filter((d) =>
    d.contacts.some((c) => c.contact_id === contact.id),
  )
  if (list.isLoading) return <p className="text-sm text-steel-400">Loading</p>
  if (deals.length === 0) {
    return (
      <p className="text-base text-steel-300">
        No deals linked. Link this contact from the{' '}
        <Link to="/app/deals" className="text-steel-100 hover:text-steel-050">
          Deals
        </Link>{' '}
        page.
      </p>
    )
  }
  return (
    <ul className="divide-y divide-steel-600">
      {deals.map((d) => {
        const role = d.contacts.find((c) => c.contact_id === contact.id)?.role ?? 'other'
        return (
          <li key={d.id} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
            <div>
              <p className="text-base text-steel-100">{d.name}</p>
              <p className="text-sm text-steel-400">
                {[
                  d.company?.name,
                  d.stage,
                  d.expected_close ? `closes ${formatDate(d.expected_close)}` : null,
                ]
                  .filter(Boolean)
                  .join(', ')}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge>{role.replace('_', ' ')}</Badge>
              <Badge tone={d.status === 'open' ? 'status' : d.status === 'won' ? 'strong' : 'risk'}>
                {d.status.replace('_', ' ')}
              </Badge>
              <span className="tnum text-base text-steel-100">
                {compactCurrency(d.value_cents, d.currency)}
              </span>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
