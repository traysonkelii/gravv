import { useEffect, useRef, type ReactNode } from 'react'
import { Button } from '@/components/ui/Button'

type Props = {
  open: boolean
  title: string
  children: ReactNode
  onClose: () => void
  confirmLabel?: string
  onConfirm?: () => void
  danger?: boolean
  busy?: boolean
}

/* Native <dialog>: focus trap, escape, and backdrop come from the platform. */
export function Dialog({
  open,
  title,
  children,
  onClose,
  confirmLabel,
  onConfirm,
  danger,
  busy,
}: Props) {
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
      className="m-auto w-full max-w-md border border-steel-500 bg-steel-800 p-6 text-steel-200 shadow-plate backdrop:bg-steel-950/70"
      aria-labelledby="dialog-title"
    >
      <h2 id="dialog-title" className="font-display text-xl font-bold text-steel-100">
        {title}
      </h2>
      <div className="mt-3 text-base text-steel-300">{children}</div>
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        {onConfirm && (
          <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} loading={busy}>
            {confirmLabel ?? 'Confirm'}
          </Button>
        )}
      </div>
    </dialog>
  )
}
