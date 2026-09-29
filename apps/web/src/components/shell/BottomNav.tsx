import { NavLink } from 'react-router'
import { CaptureButton } from '@/components/shell/CaptureButton'
import { primaryNav } from '@/components/shell/nav'
import { Icon } from '@/components/ui/Icon'

export function BottomNav() {
  return (
    <>
      <div
        className="fixed right-4 bottom-20 z-30 md:hidden"
        style={{ bottom: 'calc(5rem + env(safe-area-inset-bottom))' }}
      >
        <CaptureButton />
      </div>
      <nav
        aria-label="Primary"
        className="brushed fixed inset-x-0 bottom-0 z-30 bg-steel-900 md:hidden"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        <div aria-hidden className="edge-highlight" />
        <ul className="grid grid-cols-4">
          {primaryNav.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  `relative flex h-16 flex-col items-center justify-center gap-1 text-xs ${
                    isActive ? 'text-temper-500' : 'text-steel-400'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <span aria-hidden className="absolute inset-x-3 top-0 h-0.5 bg-temper-500" />
                    )}
                    <Icon icon={item.icon} size={22} />
                    <span>{item.label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </>
  )
}
