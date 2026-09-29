import { ChevronDown } from 'lucide-react'
import { Icon } from '@/components/ui/Icon'
import { useActiveWorkspace, useSwitchWorkspace } from '@/lib/workspace'

export function WorkspaceMenu() {
  const { workspace, memberships } = useActiveWorkspace()
  const switchTo = useSwitchWorkspace()
  if (!workspace) return <span className="text-sm text-steel-400">Loading</span>
  if (memberships.length <= 1)
    return <span className="text-sm text-steel-200">{workspace.workspace_name}</span>
  return (
    <label className="relative inline-flex items-center text-sm text-steel-200">
      <span className="sr-only">Workspace</span>
      <select
        value={workspace.workspace_id}
        onChange={(e) => switchTo(e.target.value)}
        className="h-9 appearance-none bg-transparent pr-6 text-steel-200 focus-visible:outline-2"
      >
        {memberships.map((m) => (
          <option key={m.workspace_id} value={m.workspace_id}>
            {m.workspace_name}
          </option>
        ))}
      </select>
      <Icon
        icon={ChevronDown}
        size={16}
        className="pointer-events-none absolute right-0 text-steel-400"
      />
    </label>
  )
}
