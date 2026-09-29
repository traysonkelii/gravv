import { Outlet } from 'react-router'
import { Tabs } from '@/components/ui/Tabs'

const tabs = [
  { key: 'profile', label: 'Profile', to: '/app/settings/profile' },
  { key: 'workspace', label: 'Workspace', to: '/app/settings/workspace' },
  { key: 'members', label: 'Members', to: '/app/settings/members' },
  { key: 'ai', label: 'AI', to: '/app/settings/ai' },
  { key: 'integrations', label: 'Integrations', to: '/app/settings/integrations' },
  { key: 'security', label: 'Security', to: '/app/settings/security' },
  { key: 'data', label: 'Data', to: '/app/settings/data' },
]

export function SettingsLayout() {
  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-steel-100">Settings</h1>
      <div className="mt-4">
        <Tabs tabs={tabs} ariaLabel="Settings sections" />
      </div>
      <div className="mt-6 max-w-2xl">
        <Outlet />
      </div>
    </div>
  )
}
