import { createBrowserRouter, Navigate } from 'react-router'
import { AppShell } from '@/components/shell/AppShell'
import { Callback } from '@/features/auth/Callback'
import { MagicLink } from '@/features/auth/MagicLink'
import { RedirectIfAuthed, RequireAuth } from '@/features/auth/RequireAuth'
import { Reset } from '@/features/auth/Reset'
import { SignIn } from '@/features/auth/SignIn'
import { SignUp } from '@/features/auth/SignUp'
import { AnalyticsPage } from '@/features/analytics/AnalyticsPage'
import { RequireOnboarded } from '@/features/auth/RequireOnboarded'
import { InsightsPage } from '@/features/insights/InsightsPage'
import { ProposalReview } from '@/features/capture/ProposalReview'
import { ContactDetail } from '@/features/contacts/ContactDetail'
import { ContactCreatePage, ContactEditPage } from '@/features/contacts/ContactForm'
import { ContactsList } from '@/features/contacts/ContactsList'
import { Home } from '@/features/home/Home'
import { InvitePage } from '@/features/invite/InvitePage'
import { Onboarding } from '@/features/onboarding/Onboarding'
import { DataSettings } from '@/features/settings/DataSettings'
import { IntegrationsSettings } from '@/features/settings/IntegrationsSettings'
import { MembersSettings } from '@/features/settings/MembersSettings'
import { ProfileSettings } from '@/features/settings/ProfileSettings'
import { SecuritySettings } from '@/features/settings/SecuritySettings'
import { SettingsLayout } from '@/features/settings/SettingsLayout'
import { WorkspaceSettings } from '@/features/settings/WorkspaceSettings'

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
  { path: '/invite/:token', element: <InvitePage /> },
  {
    element: <RequireAuth />,
    children: [
      { path: '/onboarding', element: <Onboarding /> },
      {
        element: <RequireOnboarded />,
        children: [
          {
            path: '/app',
            element: <AppShell />,
            children: [
              { index: true, element: <Navigate to="/app/home" replace /> },
              { path: 'home', element: <Home /> },
              { path: 'contacts', element: <ContactsList /> },
              { path: 'contacts/new', element: <ContactCreatePage /> },
              { path: 'contacts/:id', element: <ContactDetail /> },
              { path: 'contacts/:id/edit', element: <ContactEditPage /> },
              { path: 'captures/:id', element: <ProposalReview /> },
              { path: 'network', element: <Placeholder title="Network" /> },
              { path: 'analytics', element: <AnalyticsPage /> },
              { path: 'insights', element: <InsightsPage /> },
              { path: 'tasks', element: <Placeholder title="Tasks" /> },
              { path: 'deals', element: <Placeholder title="Deals" /> },
              {
                path: 'settings',
                element: <SettingsLayout />,
                children: [
                  { index: true, element: <Navigate to="/app/settings/profile" replace /> },
                  { path: 'profile', element: <ProfileSettings /> },
                  { path: 'workspace', element: <WorkspaceSettings /> },
                  { path: 'members', element: <MembersSettings /> },
                  { path: 'integrations', element: <IntegrationsSettings /> },
                  { path: 'security', element: <SecuritySettings /> },
                  { path: 'data', element: <DataSettings /> },
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
