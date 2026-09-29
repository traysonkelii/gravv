import { Link } from 'react-router'
import { Button } from '@/components/ui/Button'
import { ScoreBlade } from '@/components/ui/ScoreBlade'
import { StatBlock } from '@/components/ui/StatBlock'
import { Skeleton } from '@/components/ui/Skeleton'
import { useMe } from '@/lib/api/me'
import { copy } from '@/lib/copy'
import { compactCurrency, dueLabel, relativeTime, signedDelta } from '@/lib/format'
import { useUiStore } from '@/lib/store'
import { useInsights, useSummary } from '@/features/analytics/api'
import { usePendingCaptures } from '@/features/capture/api'
import { useContacts, type Contact } from '@/features/contacts/api'
import { InsightCard } from '@/features/insights/InsightCard'

function greeting(date = new Date()): string {
  const h = date.getHours()
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

function Row({ contact, meta }: { contact: Contact; meta: string }) {
  return (
    <li>
      <Link
        to={`/app/contacts/${contact.id}`}
        className="flex min-h-12 items-center gap-3 border-b border-steel-600 py-2 hover:bg-steel-700"
      >
        <div className="min-w-0 flex-1">
          <p className="truncate text-base text-steel-100">
            {contact.honorific ? `${contact.honorific} ` : ''}
            {contact.display_name}
          </p>
          <p className="truncate text-sm text-steel-400">
            {[contact.company?.name, contact.title].filter(Boolean).join(', ')}
          </p>
        </div>
        <div className="hidden w-40 sm:block">
          <ScoreBlade score={contact.gravity_score} band={contact.band} showLabel={false} />
        </div>
        <span className="tnum w-12 text-right text-sm text-steel-100">{contact.gravity_score}</span>
        <span className="w-32 text-right text-sm text-steel-400">{meta}</span>
      </Link>
    </li>
  )
}

function Section({
  title,
  to,
  children,
}: {
  title: string
  to: string
  children: React.ReactNode
}) {
  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between">
        <h2 className="text-md font-semibold text-steel-100">{title}</h2>
        <Link to={to} className="text-sm text-steel-400 hover:text-steel-200">
          See all
        </Link>
      </div>
      <div className="mt-2">{children}</div>
    </section>
  )
}

export function PendingCaptures() {
  const { data } = usePendingCaptures()
  const items = (data ?? []).filter((c) => c.status !== 'confirmed' && c.status !== 'discarded')
  if (items.length === 0) return null
  return (
    <section className="mt-8">
      <h2 className="text-md font-semibold text-steel-100">Pending captures</h2>
      <ul className="mt-2 divide-y divide-steel-600 border-y border-steel-600">
        {items.map((c) => (
          <li key={c.id} className="flex h-14 items-center justify-between gap-4 text-sm">
            <span className="text-steel-200">
              {c.kind === 'voice' ? 'Voice note' : 'Text note'}, {relativeTime(c.created_at)},{' '}
              <span className="text-steel-400">
                {c.status === 'proposed'
                  ? 'needs review'
                  : c.status === 'failed'
                    ? 'failed'
                    : 'processing'}
              </span>
            </span>
            <Link to={`/app/captures/${c.id}`} className="text-steel-100 hover:text-steel-050">
              Review
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function Home() {
  const { data: me } = useMe()
  const openCapture = useUiStore((s) => s.openCapture)
  const name = me?.profile.full_name.split(' ')[0] ?? ''
  const summary = useSummary('week', 'me')
  const due = useContacts({ sort: 'next_due', owner: 'me' })
  const recent = useContacts({ sort: 'last_interaction' })
  const insights = useInsights('me', 'new', 3)
  const dueItems = (due.data?.pages[0]?.items ?? []).filter((c) => c.next_due_at).slice(0, 3)
  const recentItems = (recent.data?.pages[0]?.items ?? [])
    .filter((c) => c.last_interaction)
    .slice(0, 3)
  const s = summary.data
  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-steel-100">
        {greeting()}
        {name ? `, ${name}.` : '.'}
      </h1>
      <div aria-hidden className="hamon my-6" />
      {s ? (
        <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
          <StatBlock
            value={String(s.contact_count)}
            label={copy.contacts}
            delta={
              s.contact_count_delta
                ? {
                    text: `${signedDelta(s.contact_count_delta)} this week`,
                    negative: s.contact_count_delta < 0,
                  }
                : undefined
            }
          />
          <StatBlock
            value={String(s.avg_gravity)}
            label={copy.avgGravity}
            delta={
              s.avg_gravity_delta
                ? {
                    text: `${signedDelta(s.avg_gravity_delta)} this week`,
                    negative: s.avg_gravity_delta < 0,
                  }
                : undefined
            }
          />
          <StatBlock value={String(s.due_count)} label={copy.dueThisWeek} />
          <StatBlock
            value={compactCurrency(s.pipeline_value_cents)}
            label={copy.pipeline}
            delta={
              s.pipeline_delta_pct
                ? {
                    text: `${signedDelta(s.pipeline_delta_pct, '%')}`,
                    negative: s.pipeline_delta_pct < 0,
                  }
                : undefined
            }
          />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-6 md:grid-cols-4" aria-busy>
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      )}
      <Section title="Due next" to="/app/contacts?sort=next_due">
        {dueItems.length ? (
          <ul>
            {dueItems.map((c) => (
              <Row key={c.id} contact={c} meta={dueLabel(c.next_due_at)} />
            ))}
          </ul>
        ) : (
          <p className="text-sm text-steel-400">
            Nothing coming due. Add contacts or log a note to start orbits.
          </p>
        )}
      </Section>
      <Section title="Recent" to="/app/contacts?sort=last_interaction">
        {recentItems.length ? (
          <ul>
            {recentItems.map((c) => (
              <Row key={c.id} contact={c} meta={relativeTime(c.last_interaction?.occurred_at)} />
            ))}
          </ul>
        ) : (
          <div className="flex flex-col items-start gap-2">
            <p className="text-sm text-steel-400">No interactions yet.</p>
            <Button variant="primary" onClick={() => openCapture()}>
              Capture a note
            </Button>
          </div>
        )}
      </Section>
      <Section title="Insights" to="/app/insights">
        {(insights.data ?? []).length ? (
          (insights.data ?? []).map((i) => <InsightCard key={i.id} insight={i} compact />)
        ) : (
          <p className="text-sm text-steel-400">Nothing to flag right now.</p>
        )}
      </Section>
      <PendingCaptures />
    </div>
  )
}
