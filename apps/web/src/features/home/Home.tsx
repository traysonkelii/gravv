import { useAuth } from '@/lib/auth'

function greeting(date = new Date()): string {
  const h = date.getHours()
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

export function Home() {
  const { user } = useAuth()
  const name = (user?.user_metadata?.full_name as string | undefined)?.split(' ')[0] ?? ''
  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-steel-100">
        {greeting()}
        {name ? `, ${name}.` : '.'}
      </h1>
      <p className="mt-2 text-sm text-steel-400">
        Your workspace is ready. Contacts, capture, and insights arrive in the next milestones.
      </p>
    </div>
  )
}
