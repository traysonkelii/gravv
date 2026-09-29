import { useState } from 'react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/Button'
import { Chip } from '@/components/ui/Chip'
import { Select } from '@/components/ui/Field'
import { Plate } from '@/components/ui/Plate'
import { Skeleton } from '@/components/ui/Skeleton'
import { copy, type Band } from '@/lib/copy'
import { compactCurrency, relativeTime } from '@/lib/format'
import { useGraph, usePaths, type GraphFilters, type GraphNode } from '@/features/network/api'
import { NetworkCanvas } from '@/features/network/NetworkCanvas'

const relTypes = ['client', 'partner', 'vendor', 'colleague', 'government', 'other']
const bands: Band[] = ['strong', 'steady', 'weak', 'drifting']

export function NetworkPage() {
  const [filters, setFilters] = useState<GraphFilters>({ min_score: 0 })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [pathTarget, setPathTarget] = useState<string | null>(null)
  const [resetSignal, setResetSignal] = useState(0)
  const [exportSignal, setExportSignal] = useState(0)
  const { data, isLoading } = useGraph(filters)
  const paths = usePaths('me', pathTarget)
  const nodes = data?.nodes ?? []
  const edges = data?.edges ?? []
  const selected: GraphNode | null = nodes.find((n) => n.id === selectedId) ?? null
  const industries = Array.from(
    new Set(nodes.map((n) => n.industry).filter((x): x is string => !!x)),
  ).sort()
  const companies = Array.from(
    new Set(nodes.map((n) => n.company).filter((x): x is string => !!x)),
  ).sort()
  const mutual = selected
    ? edges
        .filter((e) => e.source !== 'me' && (e.source === selected.id || e.target === selected.id))
        .map((e) => nodes.find((n) => n.id === (e.source === selected.id ? e.target : e.source)))
        .filter((n): n is GraphNode => !!n)
    : []
  const highlight = paths.data?.paths[0]?.nodes ?? null

  return (
    <div className="fill-below-bar -mx-4 -mt-4 flex flex-col md:-mx-8 md:flex-row">
      <aside
        className="flex w-full shrink-0 flex-col gap-4 border-b border-steel-600 bg-steel-900 p-4 md:w-72 md:border-r md:border-b-0"
        aria-label="Network filters"
      >
        <h1 className="font-display text-2xl font-bold text-steel-100">{copy.nav.network}</h1>
        <div>
          <p className="text-sm text-steel-300">Relationship type</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {relTypes.map((r) => (
              <Chip
                key={r}
                label={r[0]!.toUpperCase() + r.slice(1)}
                selected={filters.relationship_type === r}
                onClick={() =>
                  setFilters({
                    ...filters,
                    relationship_type: filters.relationship_type === r ? undefined : r,
                  })
                }
              />
            ))}
          </div>
        </div>
        <Select
          label="Industry"
          value={filters.industry ?? ''}
          onChange={(e) => setFilters({ ...filters, industry: e.target.value || undefined })}
        >
          <option value="">All industries</option>
          {industries.map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </Select>
        <label className="flex flex-col gap-1 text-sm text-steel-300">
          Minimum gravity: <span className="tnum text-steel-100">{filters.min_score ?? 0}</span>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={filters.min_score ?? 0}
            onChange={(e) => setFilters({ ...filters, min_score: Number(e.target.value) })}
            className="accent-steel-050"
          />
        </label>
        <div>
          <p className="text-sm text-steel-300">Legend</p>
          <ul className="mt-2 flex flex-col gap-1 text-sm text-steel-300">
            {bands.map((b) => (
              <li key={b} className="flex items-center gap-2">
                <span
                  aria-hidden
                  className="inline-block size-3"
                  style={{ backgroundColor: `var(--color-band-${b})` }}
                />
                {copy.band[b]}
              </li>
            ))}
          </ul>
        </div>
        <Select
          label="Find a path to"
          value={pathTarget ?? ''}
          onChange={(e) => setPathTarget(e.target.value || null)}
        >
          <option value="">Pick a target</option>
          <optgroup label="Companies">
            {companies.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </optgroup>
          <optgroup label="Contacts">
            {nodes
              .filter((n) => n.kind === 'contact')
              .map((n) => (
                <option key={n.id} value={n.id}>
                  {n.display_name}
                </option>
              ))}
          </optgroup>
        </Select>
        {pathTarget && (
          <p className="text-sm text-steel-300" aria-live="polite">
            {paths.isLoading
              ? 'Looking for a path.'
              : paths.isError || !paths.data?.paths.length
                ? 'No path found within four hops.'
                : `Path: ${paths.data.paths[0]!.nodes.map((id) => nodes.find((n) => n.id === id)?.display_name ?? id).join(' to ')}`}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => setResetSignal((s) => s + 1)}>Reset view</Button>
          <Button onClick={() => setExportSignal((s) => s + 1)}>Export PNG</Button>
        </div>
      </aside>
      <div className="relative min-h-80 flex-1 bg-steel-950">
        {isLoading ? (
          <Skeleton className="h-full w-full" />
        ) : (
          <NetworkCanvas
            nodes={nodes}
            edges={edges}
            selectedId={selectedId}
            highlightPath={highlight}
            onSelect={setSelectedId}
            resetSignal={resetSignal}
            exportSignal={exportSignal}
          />
        )}
        {selected && selected.kind === 'contact' && (
          <Plate className="absolute right-4 bottom-4 w-72" aria-label="Selected contact">
            <h2 className="font-display text-lg font-bold text-steel-100">
              {selected.display_name}
            </h2>
            <p className="text-sm text-steel-400">
              {[selected.company, selected.title].filter(Boolean).join(', ')}
            </p>
            <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
              <dt className="text-steel-400">{copy.gravity}</dt>
              <dd className="tnum text-steel-100">
                {selected.gravity_score}{' '}
                <span className="text-steel-400">{copy.band[selected.band as Band]}</span>
              </dd>
              <dt className="text-steel-400">Connections</dt>
              <dd className="tnum text-steel-100">{selected.connection_count}</dd>
              <dt className="text-steel-400">Last contact</dt>
              <dd className="text-steel-100">{relativeTime(selected.last_interaction_at)}</dd>
              <dt className="text-steel-400">Deal value</dt>
              <dd className="tnum text-steel-100">
                {selected.deal_value_cents ? compactCurrency(selected.deal_value_cents) : 'none'}
              </dd>
            </dl>
            <p className="mt-3 text-sm text-steel-400">Mutual connections</p>
            <ul className="text-sm text-steel-200">
              {mutual.length ? (
                mutual.map((m) => <li key={m.id}>{m.display_name}</li>)
              ) : (
                <li className="text-steel-400">None recorded</li>
              )}
            </ul>
            <div className="mt-3 flex justify-end">
              <Link
                to={`/app/contacts/${selected.id}`}
                className="text-sm text-steel-100 hover:text-steel-050"
              >
                Open profile
              </Link>
            </div>
          </Plate>
        )}
      </div>
    </div>
  )
}
