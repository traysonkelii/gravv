import { Bell, LogOut, Search } from 'lucide-react'
import { IconButton } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { useAuth } from '@/lib/auth'
import { copy } from '@/lib/copy'

export function TopBar({ workspaceName = 'Personal' }: { workspaceName?: string }) {
  const { signOut } = useAuth()
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-steel-600 bg-steel-900 px-4 md:px-8">
      <span className="font-display text-lg font-bold text-steel-100 md:hidden">
        {copy.appName}
      </span>
      <span className="hidden text-sm text-steel-300 md:inline">{workspaceName}</span>
      <div className="ml-auto flex items-center">
        <IconButton label="Search">
          <Icon icon={Search} />
        </IconButton>
        <IconButton label="Notifications">
          <Icon icon={Bell} />
        </IconButton>
        <IconButton label="Sign out" onClick={() => void signOut()}>
          <Icon icon={LogOut} />
        </IconButton>
      </div>
    </header>
  )
}
