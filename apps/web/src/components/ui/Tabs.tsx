import { NavLink } from 'react-router'
import type { KeyboardEvent } from 'react'

export type Tab = { key: string; label: string; to?: string }

type Props = {
  tabs: Tab[]
  value?: string
  onChange?: (key: string) => void
  ariaLabel: string
}

/* Text tabs; the active one carries a 2px temper underline whose right end is chamfered like a blade tip.
   Works as links (to) or as a controlled tablist (value/onChange). Arrow keys move between tabs. */
export function Tabs({ tabs, value, onChange, ariaLabel }: Props) {
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!onChange || !value) return
    const idx = tabs.findIndex((t) => t.key === value)
    if (e.key === 'ArrowRight') onChange(tabs[(idx + 1) % tabs.length]!.key)
    if (e.key === 'ArrowLeft') onChange(tabs[(idx - 1 + tabs.length) % tabs.length]!.key)
  }
  const cls = (active: boolean) =>
    `relative flex h-11 shrink-0 items-center px-3 text-sm ${active ? 'text-steel-100' : 'text-steel-400 hover:text-steel-200'}`
  return (
    <div
      role={onChange ? 'tablist' : 'navigation'}
      aria-label={ariaLabel}
      onKeyDown={onKey}
      className="flex overflow-x-auto border-b border-steel-600"
    >
      {tabs.map((t) =>
        t.to ? (
          <NavLink key={t.key} to={t.to} className={({ isActive }) => cls(isActive)}>
            {({ isActive }) => (
              <>
                {t.label}
                {isActive && (
                  <span
                    aria-hidden
                    className="chamfer-tr absolute inset-x-0 -bottom-px h-0.5 bg-temper-500"
                  />
                )}
              </>
            )}
          </NavLink>
        ) : (
          <button
            key={t.key}
            role="tab"
            type="button"
            aria-selected={value === t.key}
            tabIndex={value === t.key ? 0 : -1}
            onClick={() => onChange?.(t.key)}
            className={cls(value === t.key)}
          >
            {t.label}
            {value === t.key && (
              <span
                aria-hidden
                className="chamfer-tr absolute inset-x-0 -bottom-px h-0.5 bg-temper-500"
              />
            )}
          </button>
        ),
      )}
    </div>
  )
}
