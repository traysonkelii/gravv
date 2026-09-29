import { useNavigate } from 'react-router'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { toast, toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import { formatDate } from '@/lib/format'
import { useInsightAct, useInsightStatus, type Insight } from '@/features/analytics/api'

const actionLabel: Record<string, string> = {
  create_task: 'Create task',
  open_contact: 'Open contact',
  open_company: 'Open company',
  open_analytics: 'Open analytics',
  draft_message: 'Open contact',
  open_brief: 'Read brief',
}

function evidenceLine(i: Insight): string | null {
  const e = i.evidence as Record<string, unknown>
  const parts: string[] = []
  if (typeof e.interactions === 'number')
    parts.push(`Based on ${e.interactions} interaction${e.interactions === 1 ? '' : 's'}`)
  if (typeof e.last_interaction_at === 'string')
    parts.push(`last on ${formatDate(e.last_interaction_at)}`)
  if (typeof e.score === 'number') parts.push(`gravity ${e.score}`)
  if (typeof e.active_contacts === 'number') parts.push(`${e.active_contacts} contacts active`)
  if (typeof e.fact === 'string') parts.push(`fact: ${e.fact}`)
  return parts.length ? parts.join(', ') : null
}

export function InsightCard({ insight, compact = false }: { insight: Insight; compact?: boolean }) {
  const navigate = useNavigate()
  const act = useInsightAct()
  const setStatus = useInsightStatus()
  const action = insight.suggested_action as { type?: string } | null
  const label = action?.type ? (actionLabel[action.type] ?? 'Open') : null
  const evidence = evidenceLine(insight)
  return (
    <article className={`border-b border-steel-600 py-3 ${compact ? '' : 'md:py-4'}`}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-base text-steel-100">{insight.title}</h3>
        <Badge tone={insight.severity === 'warning' ? 'risk' : 'status'}>{insight.severity}</Badge>
        {insight.kind === 'briefing' && <Badge>brief</Badge>}
      </div>
      <p
        className={`mt-1 text-sm text-steel-300 ${insight.kind === 'briefing' ? 'whitespace-pre-wrap' : ''}`}
      >
        {insight.body}
      </p>
      {evidence && <p className="mt-1 text-sm text-steel-400">{evidence}</p>}
      {insight.status === 'new' || insight.status === 'seen' ? (
        <div className="mt-2 flex gap-2">
          {label && (
            <Button
              variant="primary"
              loading={act.isPending}
              onClick={async () => {
                try {
                  const res = await act.mutateAsync(insight.id)
                  if (res.task_id) toast('Task created')
                  if (res.navigate_to) navigate(res.navigate_to)
                } catch (e) {
                  toastError(
                    'Action could not be completed',
                    e instanceof ApiError ? e.problem.detail : undefined,
                  )
                }
              }}
            >
              {label}
            </Button>
          )}
          <Button
            variant="ghost"
            onClick={() => setStatus.mutate({ id: insight.id, status: 'dismissed' })}
          >
            Dismiss
          </Button>
        </div>
      ) : (
        <p className="mt-2 text-sm text-steel-400">
          {insight.status === 'acted' ? 'Acted on' : insight.status}
        </p>
      )}
    </article>
  )
}
