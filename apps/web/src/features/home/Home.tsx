import { Link } from 'react-router'
import { Button } from '@/components/ui/Button'
import { useAuth } from '@/lib/auth'
import { relativeTime } from '@/lib/format'
import { useUiStore } from '@/lib/store'
import { usePendingCaptures } from '@/features/capture/api'

function greeting(date = new Date()): string {
  const h = date.getHours()
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
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
  const { user } = useAuth()
  const openCapture = useUiStore((s) => s.openCapture)
  const name = (user?.user_metadata?.full_name as string | undefined)?.split(' ')[0] ?? ''
  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-steel-100">
        {greeting()}
        {name ? `, ${name}.` : '.'}
      </h1>
      <p className="mt-2 text-sm text-steel-400">
        Capture a note about someone you met and Gravv turns it into facts and follow-ups.
      </p>
      <div className="mt-4">
        <Button variant="primary" onClick={() => openCapture()}>
          Capture a note
        </Button>
      </div>
      <PendingCaptures />
    </div>
  )
}
