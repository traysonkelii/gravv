import { useState } from 'react'
import { Link } from 'react-router'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Badge } from '@/components/ui/Badge'
import { Chip } from '@/components/ui/Chip'
import { Input } from '@/components/ui/Field'
import { Plate } from '@/components/ui/Plate'
import { Skeleton } from '@/components/ui/Skeleton'
import { StatBlock } from '@/components/ui/StatBlock'
import { Table, TD, TH, THead, TR } from '@/components/ui/Table'
import { Tabs } from '@/components/ui/Tabs'
import { bandColor, chart, kindShade } from '@/lib/chartTheme'
import { copy, type Band } from '@/lib/copy'
import { compactCurrency, formatDate, relativeTime, signedDelta } from '@/lib/format'
import { useActiveWorkspace } from '@/lib/workspace'
import {
  useDistribution,
  useInsights,
  useInteractionSeries,
  useSummary,
  useTeam,
  useTopContacts,
  type Range,
  type Scope,
} from '@/features/analytics/api'
import { InsightCard } from '@/features/insights/InsightCard'

const ranges: { key: Range; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: 'week', label: 'Week' },
  { key: 'month', label: 'Month' },
  { key: 'quarter', label: 'Quarter' },
  { key: 'year', label: 'Year' },
]

export function AnalyticsPage() {
  const { workspace } = useActiveWorkspace()
  const isManager = workspace ? ['manager', 'admin', 'owner'].includes(workspace.role) : false
  const [range, setRange] = useState<Range>('month')
  const [scope, setScope] = useState<Scope>('me')
  const [q, setQ] = useState('')
  const summary = useSummary(range, scope)
  const dist = useDistribution(scope)
  const series = useInteractionSeries(range, scope)
  const top = useTopContacts(scope, q)
  const insights = useInsights(scope, 'new', 6)
  const team = useTeam(range, isManager && scope === 'team')
  const s = summary.data

  const periods = Array.from(new Set((series.data ?? []).map((p) => p.period))).sort()
  const kinds = Array.from(new Set((series.data ?? []).map((p) => p.kind)))
  const seriesRows = periods.map((period) => {
    const row: Record<string, string | number> = {
      period: period.slice(0, range === 'today' ? 16 : 10),
    }
    for (const k of kinds)
      row[k] = (series.data ?? [])
        .filter((p) => p.period === period && p.kind === k)
        .reduce((a, p) => a + p.count, 0)
    return row
  })

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1 className="font-display text-2xl font-bold text-steel-100">Analytics</h1>
        <div className="flex flex-wrap gap-2" aria-label="Range">
          {ranges.map((r) => (
            <Chip
              key={r.key}
              label={r.label}
              selected={range === r.key}
              onClick={() => setRange(r.key)}
            />
          ))}
        </div>
      </div>
      {isManager && (
        <div className="mt-4">
          <Tabs
            tabs={[
              { key: 'me', label: 'Mine' },
              { key: 'team', label: 'Team' },
            ]}
            value={scope}
            onChange={(k) => setScope(k as Scope)}
            ariaLabel="Analytics scope"
          />
        </div>
      )}
      <div className="mt-6 grid grid-cols-2 gap-6 md:grid-cols-4">
        {s ? (
          <>
            <StatBlock
              value={String(s.contact_count)}
              label={copy.contacts}
              delta={
                s.contact_count_delta
                  ? {
                      text: `${signedDelta(s.contact_count_delta)} vs previous`,
                      negative: s.contact_count_delta < 0,
                    }
                  : undefined
              }
            />
            <StatBlock
              value={`${Math.round(s.engagement_rate * 100)}%`}
              label="Engaged in range"
              delta={{ text: `${s.active_count} active` }}
            />
            <StatBlock
              value={String(s.avg_gravity)}
              label={copy.avgGravity}
              delta={
                s.avg_gravity_delta
                  ? {
                      text: `${signedDelta(s.avg_gravity_delta)} vs previous`,
                      negative: s.avg_gravity_delta < 0,
                    }
                  : undefined
              }
            />
            <StatBlock
              value={compactCurrency(s.pipeline_value_cents)}
              label={copy.pipeline}
              delta={{
                text: `${s.open_opportunity_count} open${s.pipeline_delta_pct ? `, ${signedDelta(s.pipeline_delta_pct, '%')}` : ''}`,
                negative: s.pipeline_delta_pct < 0,
              }}
            />
          </>
        ) : (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)
        )}
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <Plate as="section" aria-label="Distribution by band">
          <h2 className="text-md font-semibold text-steel-100">Relationships by band</h2>
          <div className="mt-4 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={(dist.data ?? []).map((d) => ({ ...d, label: copy.band[d.band as Band] }))}
                barCategoryGap={8}
              >
                <CartesianGrid vertical={false} {...chart.grid} />
                <XAxis
                  dataKey="label"
                  {...chart.axis}
                  tickLine={false}
                  axisLine={{ stroke: chart.axis.stroke }}
                />
                <YAxis
                  allowDecimals={false}
                  {...chart.axis}
                  tickLine={false}
                  axisLine={false}
                  width={28}
                />
                <Tooltip {...chart.tooltip} />
                <Bar
                  dataKey="count"
                  isAnimationActive={false}
                  stroke="var(--color-steel-900)"
                  strokeWidth={1}
                  shape={(props: {
                    x?: number
                    y?: number
                    width?: number
                    height?: number
                    payload?: { band: string }
                  }) => (
                    <rect
                      x={props.x}
                      y={props.y}
                      width={props.width}
                      height={props.height}
                      fill={bandColor(props.payload?.band ?? 'steady')}
                      stroke="var(--color-steel-900)"
                    />
                  )}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ul className="mt-2 flex flex-wrap gap-4 text-sm text-steel-300">
            {(dist.data ?? []).map((d) => (
              <li key={d.band} className="flex items-center gap-2">
                <span
                  aria-hidden
                  className="inline-block size-3"
                  style={{ backgroundColor: bandColor(d.band) }}
                />
                {copy.band[d.band as Band]} <span className="tnum text-steel-100">{d.count}</span>
              </li>
            ))}
          </ul>
        </Plate>
        <Plate as="section" aria-label="Interactions over time">
          <h2 className="text-md font-semibold text-steel-100">Interactions over time</h2>
          <div className="mt-4 h-56">
            {seriesRows.length === 0 ? (
              <p className="text-sm text-steel-400">No interactions in this range.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={seriesRows} barCategoryGap={4}>
                  <CartesianGrid vertical={false} {...chart.grid} />
                  <XAxis
                    dataKey="period"
                    {...chart.axis}
                    tickLine={false}
                    axisLine={{ stroke: chart.axis.stroke }}
                    tickFormatter={(v: string) => v.slice(5)}
                  />
                  <YAxis
                    allowDecimals={false}
                    {...chart.axis}
                    tickLine={false}
                    axisLine={false}
                    width={28}
                  />
                  <Tooltip {...chart.tooltip} />
                  {kinds.map((k) => (
                    <Bar
                      key={k}
                      dataKey={k}
                      stackId="a"
                      fill={kindShade[k] ?? 'var(--color-steel-400)'}
                      stroke="var(--color-steel-900)"
                      strokeWidth={1}
                      isAnimationActive={false}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
          <ul className="mt-2 flex flex-wrap gap-4 text-sm text-steel-300">
            {kinds.map((k) => (
              <li key={k} className="flex items-center gap-2">
                <span
                  aria-hidden
                  className="inline-block size-3"
                  style={{ backgroundColor: kindShade[k] ?? 'var(--color-steel-400)' }}
                />
                {k}
              </li>
            ))}
          </ul>
        </Plate>
      </div>

      {scope === 'team' && isManager && (
        <section className="mt-8">
          <h2 className="text-md font-semibold text-steel-100">Team</h2>
          <Table className="mt-2">
            <THead>
              <tr>
                <TH>Member</TH>
                <TH numeric>Contacts</TH>
                <TH numeric>{copy.avgGravity}</TH>
                <TH numeric>Interactions</TH>
                <TH numeric>{copy.pipeline}</TH>
                <TH numeric>Overdue</TH>
              </tr>
            </THead>
            <tbody>
              {(team.data ?? []).map((m) => (
                <TR key={m.user_id}>
                  <TD className="text-steel-100">
                    {m.full_name} <span className="text-steel-400">{m.role}</span>
                  </TD>
                  <TD numeric>{m.contact_count}</TD>
                  <TD numeric>{m.avg_gravity}</TD>
                  <TD numeric>{m.interactions_in_range}</TD>
                  <TD numeric>{compactCurrency(m.pipeline_value_cents)}</TD>
                  <TD numeric className={m.overdue_tasks ? 'text-rust-400' : ''}>
                    {m.overdue_tasks}
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </section>
      )}

      <section className="mt-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-md font-semibold text-steel-100">Top relationships</h2>
          <Input label="Search" value={q} onChange={(e) => setQ(e.target.value)} className="w-64" />
        </div>
        <Table className="mt-2">
          <THead>
            <tr>
              <TH>Contact</TH>
              <TH>Company</TH>
              <TH numeric>{copy.gravity}</TH>
              <TH>Last interaction</TH>
              <TH numeric>Deal value</TH>
              <TH>Status</TH>
            </tr>
          </THead>
          <tbody>
            {(top.data ?? []).map((c) => (
              <TR key={c.id}>
                <TD>
                  <Link
                    to={`/app/contacts/${c.id}`}
                    className="text-steel-100 hover:text-steel-050"
                  >
                    {c.honorific ? `${c.honorific} ` : ''}
                    {c.display_name}
                  </Link>
                </TD>
                <TD className="text-steel-300">{c.company_name ?? ''}</TD>
                <TD numeric>
                  <span className="text-steel-100">{c.gravity_score}</span>{' '}
                  <span className="text-steel-400">{copy.band[c.band as Band]}</span>
                </TD>
                <TD
                  className="text-steel-300"
                  title={c.last_interaction_at ? formatDate(c.last_interaction_at) : ''}
                >
                  {relativeTime(c.last_interaction_at)}
                </TD>
                <TD numeric>{c.deal_value_cents ? compactCurrency(c.deal_value_cents) : ''}</TD>
                <TD>
                  <Badge>{copy.status[c.status as keyof typeof copy.status] ?? c.status}</Badge>
                </TD>
              </TR>
            ))}
          </tbody>
        </Table>
      </section>

      {(insights.data ?? []).length > 0 && (
        <section className="mt-8">
          <h2 className="text-md font-semibold text-steel-100">Insights</h2>
          {(insights.data ?? []).map((i) => (
            <InsightCard key={i.id} insight={i} compact />
          ))}
        </section>
      )}
    </div>
  )
}
