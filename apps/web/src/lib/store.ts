import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type UiState = {
  workspaceId: string | null
  setWorkspaceId: (id: string | null) => void
  captureOpen: boolean
  captureContactId: string | null
  openCapture: (contactId?: string | null) => void
  closeCapture: () => void
  theme: 'dark' | 'light'
  setTheme: (theme: 'dark' | 'light') => void
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      workspaceId: null,
      setWorkspaceId: (workspaceId) => set({ workspaceId }),
      captureOpen: false,
      captureContactId: null,
      openCapture: (contactId = null) => set({ captureOpen: true, captureContactId: contactId }),
      closeCapture: () => set({ captureOpen: false, captureContactId: null }),
      theme: 'dark',
      setTheme: (theme) => {
        document.documentElement.dataset.theme = theme
        set({ theme })
      },
    }),
    { name: 'gravv-ui', partialize: (s) => ({ workspaceId: s.workspaceId, theme: s.theme }) },
  ),
)
