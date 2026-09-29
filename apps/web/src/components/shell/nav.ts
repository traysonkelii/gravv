import {
  BarChart3,
  Briefcase,
  CheckSquare,
  Home,
  Lightbulb,
  Settings,
  Share2,
  Users,
  type LucideIcon,
} from 'lucide-react'
import { copy } from '@/lib/copy'

export type NavItem = { to: string; label: string; icon: LucideIcon }

export const primaryNav: NavItem[] = [
  { to: '/app/home', label: copy.nav.home, icon: Home },
  { to: '/app/contacts', label: copy.nav.contacts, icon: Users },
  { to: '/app/network', label: copy.nav.network, icon: Share2 },
  { to: '/app/analytics', label: copy.nav.analytics, icon: BarChart3 },
]

export const secondaryNav: NavItem[] = [
  { to: '/app/insights', label: copy.nav.insights, icon: Lightbulb },
  { to: '/app/tasks', label: copy.nav.tasks, icon: CheckSquare },
  { to: '/app/deals', label: copy.nav.deals, icon: Briefcase },
]

export const settingsNav: NavItem = {
  to: '/app/settings/profile',
  label: copy.nav.settings,
  icon: Settings,
}
