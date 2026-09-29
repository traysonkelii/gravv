import { useEffect, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { IconButton } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'

type Props = { open: boolean; title: string; onClose: () => void; children: ReactNode }

/* Bottom sheet on mobile, right panel on desktop. Native <dialog> provides focus trap and escape. */
export function Sheet({ open, title, onClose, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()
  }, [open])
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-labelledby="sheet-title"
      className="fixed inset-x-0 bottom-0 m-0 mt-auto sheet-h w-full max-w-none border-t border-temper-500 bg-steel-800 p-0 text-steel-200 shadow-plate backdrop:bg-steel-950/70 md:inset-y-0 md:right-0 md:left-auto md:mt-0 md:ml-auto md:h-dvh md:max-h-none md:w-105 md:border-t-0 md:border-l"
    >
      <div className="flex h-14 items-center justify-between border-b border-steel-600 px-4">
        <h2 id="sheet-title" className="font-display text-lg font-bold text-steel-100">
          {title}
        </h2>
        <IconButton label="Close" onClick={onClose}>
          <Icon icon={X} />
        </IconButton>
      </div>
      <div className="sheet-body overflow-y-auto p-4">{children}</div>
    </dialog>
  )
}
