import { create } from 'zustand'

type Toast = { id: number; title: string; detail?: string; variant: 'info' | 'error' }
type ToastState = {
  toasts: Toast[]
  push: (t: Omit<Toast, 'id'>) => void
  dismiss: (id: number) => void
}

let seq = 0
export const useToasts = create<ToastState>((set) => ({
  toasts: [],
  push: (t) => {
    const id = ++seq
    set((s) => ({ toasts: [...s.toasts, { ...t, id }].slice(-3) }))
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })), 5000)
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
}))

export function toast(title: string, detail?: string) {
  useToasts.getState().push({ title, detail, variant: 'info' })
}
export function toastError(title: string, detail?: string) {
  useToasts.getState().push({ title, detail, variant: 'error' })
}

export function ToastHost() {
  const { toasts, dismiss } = useToasts()
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-20 left-4 z-50 flex max-w-sm flex-col gap-2 md:bottom-4"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role={t.variant === 'error' ? 'alert' : 'status'}
          className={`pointer-events-auto bg-steel-700 px-4 py-3 text-sm text-steel-100 shadow-plate ${
            t.variant === 'error' ? 'border-l-2 border-rust-500' : ''
          }`}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p>{t.title}</p>
              {t.detail && (
                <details className="mt-1 text-steel-400">
                  <summary className="cursor-pointer">Details</summary>
                  <p className="mt-1">{t.detail}</p>
                </details>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="text-steel-400 hover:text-steel-100"
              aria-label="Dismiss"
            >
              Close
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
