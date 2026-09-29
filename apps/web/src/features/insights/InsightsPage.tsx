import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ListSkeleton } from '@/components/ui/Skeleton'
import { Tabs } from '@/components/ui/Tabs'
import { toast, toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import { useActiveWorkspace } from '@/lib/workspace'
import {
  useGenerateInsights,
  useInsights,
  type Insight,
  type Scope,
} from '@/features/analytics/api'
import { InsightCard } from '@/features/insights/InsightCard'

const order: Insight['severity'][] = ['warning', 'notice', 'info']
const headings: Record<Insight['severity'], string> = {
  warning: 'Needs attention',
  notice: 'Coming due',
  info: 'Worth knowing',
}

export function InsightsPage() {
  const { workspace } = useActiveWorkspace()
  const isManager = workspace ? ['manager', 'admin', 'owner'].includes(workspace.role) : false
  const [scope, setScope] = useState<Scope>('me')
  const [showAll, setShowAll] = useState(false)
  const { data, isLoading } = useInsights(scope, showAll ? 'all' : 'new')
  const generate = useGenerateInsights()
  const items = data ?? []
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1 className="font-display text-2xl font-bold text-steel-100">Insights</h1>
        {isManager && (
          <Button
            loading={generate.isPending}
            loadingLabel="Generating..."
            onClick={async () => {
              try {
                await generate.mutateAsync()
                toast('Insights are being refreshed')
              } catch (e) {
                toastError(
                  'Could not refresh insights',
                  e instanceof ApiError ? e.problem.detail : undefined,
                )
              }
            }}
          >
            Refresh insights
          </Button>
        )}
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        {isManager ? (
          <Tabs
            tabs={[
              { key: 'me', label: 'Mine' },
              { key: 'team', label: 'Team' },
            ]}
            value={scope}
            onChange={(k) => setScope(k as Scope)}
            ariaLabel="Insight scope"
          />
        ) : (
          <span />
        )}
        <Button variant="ghost" onClick={() => setShowAll((s) => !s)}>
          {showAll ? 'Show new only' : 'Show all'}
        </Button>
      </div>
      <div className="mt-4">
        {isLoading ? (
          <ListSkeleton />
        ) : items.length === 0 ? (
          <EmptyState
            title="Nothing to flag right now"
            body="Insights appear as relationships come due, drift, or share common ground with you."
          />
        ) : (
          order
            .filter((sev) => items.some((i) => i.severity === sev))
            .map((sev) => (
              <section key={sev} className="mb-8">
                <h2 className="text-md font-semibold text-steel-100">{headings[sev]}</h2>
                {items
                  .filter((i) => i.severity === sev)
                  .map((i) => (
                    <InsightCard key={i.id} insight={i} />
                  ))}
              </section>
            ))
        )}
      </div>
    </div>
  )
}
