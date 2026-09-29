import type { ReactNode } from 'react'
import { copy } from '@/lib/copy'

export function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-sm flex-col justify-center px-4 py-12">
      <p className="font-display text-xl font-bold text-steel-100">{copy.appName}</p>
      <h1 className="mt-6 font-display text-2xl font-bold text-steel-100">{title}</h1>
      <div className="mt-6">{children}</div>
    </main>
  )
}
