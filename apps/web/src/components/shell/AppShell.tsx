import { Outlet } from 'react-router'
import { BottomNav } from '@/components/shell/BottomNav'
import { SideRail } from '@/components/shell/SideRail'
import { TopBar } from '@/components/shell/TopBar'
import { CaptureSheet } from '@/features/capture/CaptureSheet'

export function AppShell() {
  return (
    <div className="flex min-h-dvh">
      <SideRail />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 pt-4 pb-28 md:px-8 md:pb-8">
          <Outlet />
        </main>
        <BottomNav />
      </div>
      <CaptureSheet />
    </div>
  )
}
