import '@/design/fonts.css'
import '@/design/tokens.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from '@/app'
import { useUiStore } from '@/lib/store'

document.documentElement.dataset.theme = useUiStore.getState().theme

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
