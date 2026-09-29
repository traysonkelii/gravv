import { NavLink } from 'react-router'
import { CaptureButton } from '@/components/shell/CaptureButton'
import { primaryNav, secondaryNav, settingsNav, type NavItem } from '@/components/shell/nav'
import { Icon } from '@/components/ui/Icon'
import { copy } from '@/lib/copy'

function RailLink({ item }: { item: NavItem }) {
  return (
    <NavLink
      to={item.to}
      className={({ isActive }) =>
        `relative flex h-11 items-center gap-3 px-6 text-sm ${
          isActive ? 'text-temper-500' : 'text-steel-300 hover:bg-steel-700 hover:text-steel-100'
        }`
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span aria-hidden className="absolute inset-y-2 left-0 w-0.5 bg-temper-500" />
          )}
          <Icon icon={item.icon} />
          <span>{item.label}</span>
        </>
      )}
    </NavLink>
  )
}

export function SideRail() {
  return (
    <aside
      className="brushed relative hidden w-60 shrink-0 flex-col bg-steel-900 md:flex"
      aria-label="Primary"
    >
      <span aria-hidden className="absolute inset-y-0 right-0 w-px bg-steel-600" />
      <div className="flex h-14 items-center px-6 font-display text-xl font-bold text-steel-100">
        {copy.appName}
      </div>
      <nav className="flex flex-1 flex-col">
        <ul>
          {primaryNav.map((item) => (
            <li key={item.to}>
              <RailLink item={item} />
            </li>
          ))}
        </ul>
        <div aria-hidden className="mx-6 my-2 h-px bg-steel-600" />
        <ul>
          {secondaryNav.map((item) => (
            <li key={item.to}>
              <RailLink item={item} />
            </li>
          ))}
        </ul>
        <div className="mt-auto px-6 py-4">
          <CaptureButton withLabel />
        </div>
        <div aria-hidden className="mx-6 h-px bg-steel-600" />
        <ul className="pb-4">
          <li>
            <RailLink item={settingsNav} />
          </li>
        </ul>
      </nav>
    </aside>
  )
}
