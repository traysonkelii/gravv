import { useState } from 'react'
import { Link } from 'react-router'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input, Select } from '@/components/ui/Field'
import { Sheet } from '@/components/ui/Sheet'
import { ListSkeleton } from '@/components/ui/Skeleton'
import { Table, TD, TH, THead, TR } from '@/components/ui/Table'
import { Tabs } from '@/components/ui/Tabs'
import { toast, toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import { compactCurrency, formatDate } from '@/lib/format'
import { ContactPicker } from '@/features/capture/ContactPicker'
import type { Contact } from '@/features/contacts/api'
import {
  useCreateOpportunity,
  useDeleteOpportunity,
  useOpportunities,
  usePutOpportunityContact,
  useRemoveOpportunityContact,
  useUpdateOpportunity,
  type Opportunity,
  type OpportunityRole,
} from '@/features/deals/api'

const roles: OpportunityRole[] = [
  'decision_maker',
  'influencer',
  'champion',
  'blocker',
  'user',
  'other',
]
const statuses = ['open', 'won', 'lost', 'on_hold'] as const
type Status = (typeof statuses)[number]

function DealForm({ deal, onClose }: { deal: Opportunity | null; onClose: () => void }) {
  const create = useCreateOpportunity()
  const update = useUpdateOpportunity()
  const [form, setForm] = useState({
    name: deal?.name ?? '',
    company_name: deal?.company?.name ?? '',
    value: deal ? String(deal.value_cents / 100) : '',
    stage: deal?.stage ?? 'qualifying',
    probability: deal?.probability != null ? String(deal.probability) : '',
    expected_close: deal?.expected_close ?? '',
    status: (deal?.status ?? 'open') as Status,
  })
  const busy = create.isPending || update.isPending
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={async (e) => {
        e.preventDefault()
        const body = {
          name: form.name.trim(),
          company_name: form.company_name.trim() || null,
          value_cents: Math.round(Number(form.value || 0) * 100),
          stage: form.stage.trim() || 'qualifying',
          probability: form.probability === '' ? null : Number(form.probability),
          expected_close: form.expected_close || null,
          status: form.status,
        }
        try {
          if (deal) await update.mutateAsync({ id: deal.id, ...body })
          else await create.mutateAsync(body)
          toast(deal ? 'Deal saved' : 'Deal added')
          onClose()
        } catch (err) {
          toastError(
            'Deal could not be saved',
            err instanceof ApiError ? err.problem.detail : undefined,
          )
        }
      }}
    >
      <Input
        label="Name"
        required
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
        maxLength={160}
      />
      <Input
        label="Company"
        value={form.company_name}
        onChange={(e) => setForm({ ...form, company_name: e.target.value })}
        maxLength={120}
      />
      <div className="grid grid-cols-2 gap-3">
        <Input
          label="Value in USD"
          type="number"
          min={0}
          step="1"
          value={form.value}
          onChange={(e) => setForm({ ...form, value: e.target.value })}
        />
        <Input
          label="Probability %"
          type="number"
          min={0}
          max={100}
          value={form.probability}
          onChange={(e) => setForm({ ...form, probability: e.target.value })}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Input
          label="Stage"
          value={form.stage}
          onChange={(e) => setForm({ ...form, stage: e.target.value })}
          maxLength={40}
        />
        <Input
          label="Expected close"
          type="date"
          value={form.expected_close}
          onChange={(e) => setForm({ ...form, expected_close: e.target.value })}
        />
      </div>
      <Select
        label="Status"
        value={form.status}
        onChange={(e) => setForm({ ...form, status: e.target.value as Status })}
      >
        {statuses.map((s) => (
          <option key={s} value={s}>
            {s.replace('_', ' ')}
          </option>
        ))}
      </Select>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" loading={busy} disabled={!form.name.trim()}>
          {deal ? 'Save deal' : 'Add deal'}
        </Button>
      </div>
    </form>
  )
}

function DealContacts({ deal }: { deal: Opportunity }) {
  const put = usePutOpportunityContact()
  const remove = useRemoveOpportunityContact()
  const [picked, setPicked] = useState<Contact | null>(null)
  const [role, setRole] = useState<OpportunityRole>('influencer')
  return (
    <div className="flex flex-col gap-3">
      <ul className="divide-y divide-steel-600">
        {deal.contacts.map((c) => (
          <li key={c.contact_id} className="flex items-center justify-between gap-2 py-2 text-sm">
            <Link
              to={`/app/contacts/${c.contact_id}`}
              className="text-steel-100 hover:text-steel-050"
            >
              {c.honorific ? `${c.honorific} ` : ''}
              {c.display_name}
            </Link>
            <span className="flex items-center gap-2">
              <select
                aria-label={`Role for ${c.display_name}`}
                value={c.role}
                onChange={(e) =>
                  put.mutate({
                    id: deal.id,
                    contactId: c.contact_id,
                    role: e.target.value as OpportunityRole,
                  })
                }
                className="h-8 border border-steel-600 bg-steel-900 px-2 text-steel-100"
              >
                {roles.map((r) => (
                  <option key={r} value={r}>
                    {r.replace('_', ' ')}
                  </option>
                ))}
              </select>
              <Button
                variant="ghost"
                onClick={() => remove.mutate({ id: deal.id, contactId: c.contact_id })}
              >
                Remove
              </Button>
            </span>
          </li>
        ))}
        {deal.contacts.length === 0 && (
          <li className="py-2 text-sm text-steel-400">No contacts linked yet.</li>
        )}
      </ul>
      <ContactPicker value={picked} onChange={setPicked} label="Link a contact" />
      {picked && (
        <div className="flex items-end gap-2">
          <Select
            label="Role"
            value={role}
            onChange={(e) => setRole(e.target.value as OpportunityRole)}
            className="w-48"
          >
            {roles.map((r) => (
              <option key={r} value={r}>
                {r.replace('_', ' ')}
              </option>
            ))}
          </Select>
          <Button
            variant="primary"
            loading={put.isPending}
            onClick={async () => {
              await put.mutateAsync({ id: deal.id, contactId: picked.id, role })
              setPicked(null)
              toast('Contact linked')
            }}
          >
            Link contact
          </Button>
        </div>
      )}
    </div>
  )
}

export function DealsPage() {
  const [status, setStatus] = useState<Status>('open')
  const [editing, setEditing] = useState<Opportunity | null | 'new'>(null)
  const [confirm, setConfirm] = useState<Opportunity | null>(null)
  const list = useOpportunities({ status })
  const remove = useDeleteOpportunity()
  const items = list.data?.pages.flatMap((p) => p.items) ?? []
  const current =
    editing && editing !== 'new' ? (items.find((d) => d.id === editing.id) ?? editing) : null
  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <h1 className="font-display text-2xl font-bold text-steel-100">Deals</h1>
        <Button variant="primary" onClick={() => setEditing('new')}>
          Add deal
        </Button>
      </div>
      <div className="mt-4">
        <Tabs
          tabs={statuses.map((s) => ({
            key: s,
            label: s[0]!.toUpperCase() + s.slice(1).replace('_', ' '),
          }))}
          value={status}
          onChange={(k) => setStatus(k as Status)}
          ariaLabel="Deal status"
        />
      </div>
      <div className="mt-2">
        {list.isLoading ? (
          <ListSkeleton />
        ) : items.length === 0 ? (
          <EmptyState
            title="No deals here"
            body="Add a deal and link the people who influence it."
            action={
              <Button variant="primary" onClick={() => setEditing('new')}>
                Add deal
              </Button>
            }
          />
        ) : (
          <Table>
            <THead>
              <tr>
                <TH>Deal</TH>
                <TH>Company</TH>
                <TH>Stage</TH>
                <TH numeric>Value</TH>
                <TH numeric>Probability</TH>
                <TH>Close</TH>
                <TH>People</TH>
                <TH />
              </tr>
            </THead>
            <tbody>
              {items.map((d) => (
                <TR key={d.id}>
                  <TD className="text-steel-100">{d.name}</TD>
                  <TD className="text-steel-300">{d.company?.name ?? ''}</TD>
                  <TD>
                    <Badge>{d.stage}</Badge>
                  </TD>
                  <TD numeric>{compactCurrency(d.value_cents, d.currency)}</TD>
                  <TD numeric>{d.probability != null ? `${d.probability}%` : ''}</TD>
                  <TD className="tnum text-steel-300">
                    {d.expected_close ? formatDate(d.expected_close) : ''}
                  </TD>
                  <TD className="text-steel-300">{d.contacts.length}</TD>
                  <TD className="text-right">
                    <Button variant="ghost" onClick={() => setEditing(d)}>
                      Open
                    </Button>
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        )}
      </div>
      <Sheet
        open={editing !== null}
        title={editing === 'new' ? 'Add deal' : (current?.name ?? 'Deal')}
        onClose={() => setEditing(null)}
      >
        {editing === 'new' && <DealForm deal={null} onClose={() => setEditing(null)} />}
        {current && (
          <div className="flex flex-col gap-8">
            <DealForm deal={current} onClose={() => setEditing(null)} />
            <section>
              <h3 className="text-md font-semibold text-steel-100">People on this deal</h3>
              <div className="mt-2">
                <DealContacts deal={current} />
              </div>
            </section>
            <Button variant="danger" onClick={() => setConfirm(current)}>
              Delete deal
            </Button>
          </div>
        )}
      </Sheet>
      <Dialog
        open={confirm !== null}
        title={`Delete ${confirm?.name ?? ''}`}
        onClose={() => setConfirm(null)}
        confirmLabel="Delete deal"
        danger
        busy={remove.isPending}
        onConfirm={async () => {
          if (!confirm) return
          await remove.mutateAsync(confirm.id)
          toast('Deal deleted')
          setConfirm(null)
          setEditing(null)
        }}
      >
        The deal and its contact links are removed from pipeline totals.
      </Dialog>
    </div>
  )
}
