import { Calendar, Mail, MoreHorizontal, Phone } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router'
import { Avatar } from '@/components/ui/Avatar'
import { Button, IconButton } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Icon } from '@/components/ui/Icon'
import { ScoreBlade } from '@/components/ui/ScoreBlade'
import { Skeleton } from '@/components/ui/Skeleton'
import { Tabs } from '@/components/ui/Tabs'
import { toast, toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import { useMe } from '@/lib/api/me'
import { copy } from '@/lib/copy'
import { useUiStore } from '@/lib/store'
import { useActiveWorkspace, useSwitchWorkspace } from '@/lib/workspace'
import {
  useContact,
  useCopyToPersonal,
  useDeleteContact,
  useShareContact,
  type Contact,
} from '@/features/contacts/api'
import { OverviewTab } from '@/features/contacts/tabs/OverviewTab'
import { HistoryTab } from '@/features/contacts/tabs/HistoryTab'
import { NotesTab } from '@/features/contacts/tabs/NotesTab'

const tabs = [
  { key: 'overview', label: 'Overview' },
  { key: 'history', label: 'History' },
  { key: 'notes', label: copy.notesToRemember },
  { key: 'tasks', label: 'Tasks' },
  { key: 'deals', label: 'Deals' },
]

function Actions({ contact }: { contact: Contact }) {
  const navigate = useNavigate()
  const openCapture = useUiStore((s) => s.openCapture)
  const { workspace, memberships } = useActiveWorkspace()
  const { data: me } = useMe()
  const switchTo = useSwitchWorkspace()
  const share = useShareContact(contact.id)
  const copyBack = useCopyToPersonal(contact.id)
  const remove = useDeleteContact()
  const [menu, setMenu] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const email = contact.emails[0]
  const phone = contact.phones[0]
  const isOwner = me?.profile.id === contact.owner_user_id
  const canEdit =
    isOwner || (workspace ? ['manager', 'admin', 'owner'].includes(workspace.role) : false)
  const canDelete = isOwner || (workspace ? ['admin', 'owner'].includes(workspace.role) : false)
  const orgs = memberships.filter((m) => m.kind === 'organization' && m.role !== 'viewer')
  const inPersonal = workspace?.kind === 'personal'

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button onClick={() => phone && (window.location.href = `tel:${phone}`)} disabled={!phone}>
        <Icon icon={Phone} size={16} /> Call
      </Button>
      <Button onClick={() => email && (window.location.href = `mailto:${email}`)} disabled={!email}>
        <Icon icon={Mail} size={16} /> Email
      </Button>
      <Button
        onClick={() => {
          const start = new Date(Date.now() + 86400000)
          const iso = start.toISOString().replace(/[-:]|\.\d{3}/g, '')
          const end = new Date(start.getTime() + 1800000).toISOString().replace(/[-:]|\.\d{3}/g, '')
          window.open(
            `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(`Meeting with ${contact.display_name}`)}&dates=${iso}/${end}${email ? `&add=${encodeURIComponent(email)}` : ''}`,
            '_blank',
            'noopener',
          )
        }}
      >
        <Icon icon={Calendar} size={16} /> Schedule
      </Button>
      <Button variant="primary" onClick={() => openCapture(contact.id)}>
        Capture note
      </Button>
      <div className="relative">
        <IconButton
          label="More actions"
          onClick={() => setMenu((m) => !m)}
          aria-expanded={menu}
          aria-haspopup="menu"
        >
          <Icon icon={MoreHorizontal} />
        </IconButton>
        {menu && (
          <ul
            role="menu"
            className="absolute right-0 z-10 mt-1 w-64 border border-steel-600 bg-steel-800 py-1 text-sm shadow-plate"
            onMouseLeave={() => setMenu(false)}
          >
            {canEdit && (
              <li role="none">
                <button
                  role="menuitem"
                  className="block w-full px-3 py-2 text-left text-steel-200 hover:bg-steel-700"
                  onClick={() => navigate(`/app/contacts/${contact.id}/edit`)}
                >
                  Edit contact
                </button>
              </li>
            )}
            {inPersonal &&
              orgs.map((o) => (
                <li role="none" key={o.workspace_id}>
                  <button
                    role="menuitem"
                    className="block w-full px-3 py-2 text-left text-steel-200 hover:bg-steel-700"
                    onClick={async () => {
                      try {
                        const shared = await share.mutateAsync(o.workspace_id)
                        toast('Contact shared', `A copy now lives in ${o.workspace_name}.`)
                        switchTo(o.workspace_id)
                        navigate(`/app/contacts/${shared.id}`)
                      } catch (e) {
                        toastError(
                          'Contact could not be shared',
                          e instanceof ApiError ? e.problem.detail : undefined,
                        )
                      }
                    }}
                  >
                    Share to {o.workspace_name}
                  </button>
                </li>
              ))}
            {!inPersonal && isOwner && (
              <li role="none">
                <button
                  role="menuitem"
                  className="block w-full px-3 py-2 text-left text-steel-200 hover:bg-steel-700"
                  onClick={async () => {
                    try {
                      await copyBack.mutateAsync()
                      toast('Copied to your personal workspace')
                    } catch (e) {
                      toastError(
                        'Contact could not be copied',
                        e instanceof ApiError ? e.problem.detail : undefined,
                      )
                    }
                    setMenu(false)
                  }}
                >
                  Copy to personal workspace
                </button>
              </li>
            )}
            {canDelete && (
              <li role="none">
                <button
                  role="menuitem"
                  className="block w-full px-3 py-2 text-left text-rust-400 hover:bg-steel-700"
                  onClick={() => {
                    setMenu(false)
                    setConfirmDelete(true)
                  }}
                >
                  Delete contact
                </button>
              </li>
            )}
          </ul>
        )}
      </div>
      <Dialog
        open={confirmDelete}
        title={`Delete ${contact.display_name}`}
        onClose={() => setConfirmDelete(false)}
        confirmLabel="Delete contact"
        danger
        busy={remove.isPending}
        onConfirm={async () => {
          try {
            await remove.mutateAsync(contact.id)
            toast('Contact deleted')
            navigate('/app/contacts', { replace: true })
          } catch (e) {
            toastError(
              'Contact could not be deleted',
              e instanceof ApiError ? e.problem.detail : undefined,
            )
          }
        }}
      >
        Notes, facts, and tasks for this contact are hidden with it. This can be undone within 30
        days by an admin.
      </Dialog>
    </div>
  )
}

export function ContactDetail() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') ?? 'overview'
  const { data: contact, isLoading, isError } = useContact(id)

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4" aria-busy>
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }
  if (isError || !contact) return <Navigate to="/app/contacts" replace />
  const meta = [contact.company?.name, contact.title].filter(Boolean).join(', ')

  return (
    <div>
      <Link to="/app/contacts" className="text-sm text-steel-400 hover:text-steel-200">
        Back to contacts
      </Link>
      <header className="mt-3 flex flex-col gap-4 md:flex-row md:items-start">
        <Avatar name={contact.display_name} band={contact.band} size={64} />
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-xl font-bold text-steel-100">
            {contact.honorific ? `${contact.honorific} ` : ''}
            {contact.display_name}
          </h1>
          <p className="text-sm text-steel-400">{meta || 'No company'}</p>
          <div className="mt-3 max-w-md">
            <ScoreBlade score={contact.gravity_score} band={contact.band} animate />
          </div>
        </div>
        <Actions contact={contact} />
      </header>
      <div className="mt-6">
        <Tabs
          tabs={tabs}
          value={tab}
          onChange={(k) => setParams({ tab: k })}
          ariaLabel="Contact sections"
        />
      </div>
      <div className="mt-6" role="tabpanel">
        {tab === 'overview' && <OverviewTab contact={contact} />}
        {tab === 'history' && <HistoryTab contact={contact} />}
        {tab === 'notes' && <NotesTab contact={contact} />}
        {tab === 'tasks' && (
          <p className="text-base text-steel-300">
            Tasks for this contact arrive with the tasks milestone.
          </p>
        )}
        {tab === 'deals' && (
          <p className="text-base text-steel-300">
            Linked deals arrive with the opportunities milestone.
          </p>
        )}
      </div>
    </div>
  )
}
