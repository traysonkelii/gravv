import { lazy, Suspense, type ComponentType, type ReactNode } from 'react'
import { createBrowserRouter, Navigate } from 'react-router'
import { AppShell } from '@/components/shell/AppShell'
import { Callback } from '@/features/auth/Callback'
import { MagicLink } from '@/features/auth/MagicLink'
import { RedirectIfAuthed, RequireAuth } from '@/features/auth/RequireAuth'
import { RequireOnboarded } from '@/features/auth/RequireOnboarded'
import { Reset } from '@/features/auth/Reset'
import { SignIn } from '@/features/auth/SignIn'
import { SignUp } from '@/features/auth/SignUp'
import { Landing } from '@/features/landing/Landing'

/* Feature routes load on demand so the landing and auth screens ship only the shell (Section 9.1). */
function page<T extends object>(load: () => Promise<T>, name: keyof T): ReactNode {
  const Component = lazy(async () => ({
    default: (await load())[name] as unknown as ComponentType,
  }))
  return (
    <Suspense fallback={<div className="p-8 text-sm text-steel-400">Loading</div>}>
      <Component />
    </Suspense>
  )
}

export const router = createBrowserRouter([
  { path: '/', element: <Landing /> },
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
    path: '/invite/:token',
    element: page(() => import('@/features/invite/InvitePage'), 'InvitePage'),
  },
  {
    element: <RequireAuth />,
    children: [
      {
        path: '/onboarding',
        element: page(() => import('@/features/onboarding/Onboarding'), 'Onboarding'),
      },
      {
        element: <RequireOnboarded />,
        children: [
          {
            path: '/app',
            element: <AppShell />,
            children: [
              { index: true, element: <Navigate to="/app/home" replace /> },
              { path: 'home', element: page(() => import('@/features/home/Home'), 'Home') },
              {
                path: 'contacts',
                element: page(() => import('@/features/contacts/ContactsList'), 'ContactsList'),
              },
              {
                path: 'contacts/new',
                element: page(() => import('@/features/contacts/ContactForm'), 'ContactCreatePage'),
              },
              {
                path: 'contacts/:id',
                element: page(() => import('@/features/contacts/ContactDetail'), 'ContactDetail'),
              },
              {
                path: 'contacts/:id/edit',
                element: page(() => import('@/features/contacts/ContactForm'), 'ContactEditPage'),
              },
              {
                path: 'captures/:id',
                element: page(() => import('@/features/capture/ProposalReview'), 'ProposalReview'),
              },
              {
                path: 'network',
                element: page(() => import('@/features/network/NetworkPage'), 'NetworkPage'),
              },
              {
                path: 'analytics',
                element: page(() => import('@/features/analytics/AnalyticsPage'), 'AnalyticsPage'),
              },
              {
                path: 'insights',
                element: page(() => import('@/features/insights/InsightsPage'), 'InsightsPage'),
              },
              {
                path: 'tasks',
                element: page(() => import('@/features/tasks/TasksPage'), 'TasksPage'),
              },
              {
                path: 'deals',
                element: page(() => import('@/features/deals/DealsPage'), 'DealsPage'),
              },
              {
                path: 'settings',
                element: page(() => import('@/features/settings/SettingsLayout'), 'SettingsLayout'),
                children: [
                  { index: true, element: <Navigate to="/app/settings/profile" replace /> },
                  {
                    path: 'profile',
                    element: page(
                      () => import('@/features/settings/ProfileSettings'),
                      'ProfileSettings',
                    ),
                  },
                  {
                    path: 'workspace',
                    element: page(
                      () => import('@/features/settings/WorkspaceSettings'),
                      'WorkspaceSettings',
                    ),
                  },
                  {
                    path: 'members',
                    element: page(
                      () => import('@/features/settings/MembersSettings'),
                      'MembersSettings',
                    ),
                  },
                  {
                    path: 'integrations',
                    element: page(
                      () => import('@/features/settings/IntegrationsSettings'),
                      'IntegrationsSettings',
                    ),
                  },
                  {
                    path: 'security',
                    element: page(
                      () => import('@/features/settings/SecuritySettings'),
                      'SecuritySettings',
                    ),
                  },
                  {
                    path: 'data',
                    element: page(() => import('@/features/settings/DataSettings'), 'DataSettings'),
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/app" replace /> },
])
