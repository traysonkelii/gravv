import { createBrowserRouter, Navigate } from 'react-router'
import { AppShell } from '@/components/shell/AppShell'
import { Callback } from '@/features/auth/Callback'
import { MagicLink } from '@/features/auth/MagicLink'
import { RedirectIfAuthed, RequireAuth } from '@/features/auth/RequireAuth'
import { Reset } from '@/features/auth/Reset'
import { SignIn } from '@/features/auth/SignIn'
import { SignUp } from '@/features/auth/SignUp'
import { Home } from '@/features/home/Home'

function Placeholder({ title }: { title: string }) {
  return <h1 className="font-display text-2xl font-bold text-steel-100">{title}</h1>
}

export const router = createBrowserRouter([
  { path: '/', element: <Navigate to="/app" replace /> },
  {
    path: '/auth',
    element: <RedirectIfAuthed />,
    children: [
      { path: 'sign-in', element: <SignIn /> },
      { path: 'sign-up', element: <SignUp /> },
      { path: 'magic-link', element: <MagicLink /> },
    ],
  },
  { path: '/auth/reset', element: <Reset /> },
  { path: '/auth/callback', element: <Callback /> },
  {
    element: <RequireAuth />,
    children: [
      {
        path: '/app',
        element: <AppShell />,
        children: [
          { index: true, element: <Navigate to="/app/home" replace /> },
          { path: 'home', element: <Home /> },
          { path: 'contacts', element: <Placeholder title="Contacts" /> },
          { path: 'network', element: <Placeholder title="Network" /> },
          { path: 'analytics', element: <Placeholder title="Analytics" /> },
          { path: 'insights', element: <Placeholder title="Insights" /> },
          { path: 'tasks', element: <Placeholder title="Tasks" /> },
          { path: 'deals', element: <Placeholder title="Deals" /> },
          { path: 'settings/*', element: <Placeholder title="Settings" /> },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/app" replace /> },
])
