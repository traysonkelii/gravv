import {
  Calendar,
  CheckSquare,
  FileText,
  Gift,
  Mail,
  MessageSquare,
  Phone,
  Sparkles,
  Users,
  type LucideIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Icon } from '@/components/ui/Icon'
import { formatDate, formatDateTime } from '@/lib/format'
import type { Band } from '@/lib/copy'

export type TimelineItem = {
  id: string
  ts: string
  kind: string
  title: string
  body: string
  band?: Band
  actions?: ReactNode
}

const icons: Record<string, LucideIcon> = {
  note: FileText,
  meeting: Users,
  call: Phone,
  email: Mail,
  message: MessageSquare,
  event: Calendar,
  introduction: Users,
  gift: Gift,
  task: CheckSquare,
  score: Sparkles,
  other: FileText,
}

function dayKey(iso: string): string {
  return formatDate(iso)
}

/* 2px rail, 8px square markers (band color for score changes, steel-300 for interactions), grouped by day. */
export function Timeline({ items, timeZone }: { items: TimelineItem[]; timeZone?: string }) {
  const groups: { day: string; items: TimelineItem[] }[] = []
  for (const item of items) {
    const day = dayKey(item.ts)
    const last = groups[groups.length - 1]
    if (last && last.day === day) last.items.push(item)
    else groups.push({ day, items: [item] })
  }
  return (
    <ol className="flex flex-col gap-6">
      {groups.map((g) => (
        <li key={g.day}>
          <h3 className="text-sm text-steel-400">{g.day}</h3>
          <ol className="mt-2 border-l-2 border-steel-600">
            {g.items.map((item) => (
              <li key={item.id} className="relative pl-6 pb-5 last:pb-0">
                <span
                  aria-hidden
                  className="absolute top-1.5 -left-1.25 size-2"
                  style={{
                    backgroundColor:
                      item.kind === 'score'
                        ? `var(--color-band-${item.band ?? 'steady'})`
                        : 'var(--color-steel-300)',
                  }}
                />
                <div className="flex items-start gap-2">
                  <Icon
                    icon={icons[item.kind] ?? FileText}
                    size={16}
                    className="mt-1 shrink-0 text-steel-400"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="text-base text-steel-100">{item.title}</span>
                      <span className="tnum text-sm text-steel-400">
                        {formatDateTime(item.ts, timeZone)}
                      </span>
                    </div>
                    {item.body && <p className="mt-1 text-sm text-steel-300">{item.body}</p>}
                    {item.actions && <div className="mt-2 flex gap-2">{item.actions}</div>}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </li>
      ))}
    </ol>
  )
}
