import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useNavigate, useParams } from 'react-router'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { Input, Select } from '@/components/ui/Field'
import { toast, toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import {
  useContact,
  useCreateContact,
  useUpdateContact,
  type Contact,
} from '@/features/contacts/api'

const schema = z.object({
  honorific: z.string().max(20),
  first_name: z.string().min(1, 'Enter a first name').max(80),
  last_name: z.string().max(80),
  title: z.string().max(120),
  company_name: z.string().max(120),
  emails: z.string(),
  phones: z.string(),
  location: z.string().max(120),
  relationship_type: z.enum(['client', 'partner', 'vendor', 'colleague', 'government', 'other']),
  visibility: z.enum(['team', 'private']),
  tags: z.string(),
  cadence_days: z.number().int().min(1).max(365),
})
type Form = z.infer<typeof schema>

const split = (s: string) =>
  s
    .split(/[,\n]/)
    .map((x) => x.trim())
    .filter(Boolean)

function toBody(v: Form) {
  return {
    honorific: v.honorific || null,
    first_name: v.first_name,
    last_name: v.last_name,
    title: v.title || null,
    company_name: v.company_name || null,
    emails: split(v.emails),
    phones: split(v.phones),
    location: v.location || null,
    relationship_type: v.relationship_type,
    visibility: v.visibility,
    tags: split(v.tags),
    cadence_days: v.cadence_days,
  }
}

function Form({ contact }: { contact?: Contact }) {
  const navigate = useNavigate()
  const create = useCreateContact()
  const update = useUpdateContact(contact?.id ?? '')
  const { register, handleSubmit, formState } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: {
      honorific: contact?.honorific ?? '',
      first_name: contact?.first_name ?? '',
      last_name: contact?.last_name ?? '',
      title: contact?.title ?? '',
      company_name: contact?.company?.name ?? '',
      emails: contact?.emails.join(', ') ?? '',
      phones: contact?.phones.join(', ') ?? '',
      location: contact?.location ?? '',
      relationship_type: contact?.relationship_type ?? 'other',
      visibility: contact?.visibility ?? 'team',
      tags: contact?.tags.join(', ') ?? '',
      cadence_days: contact?.cadence_days ?? 30,
    },
  })
  const busy = create.isPending || update.isPending
  return (
    <form
      className="flex max-w-2xl flex-col gap-4"
      noValidate
      onSubmit={handleSubmit(async (v) => {
        try {
          const body = toBody(v)
          const saved = contact ? await update.mutateAsync(body) : await create.mutateAsync(body)
          toast(contact ? 'Contact saved' : 'Contact added')
          navigate(`/app/contacts/${saved.id}`, { replace: true })
        } catch (e) {
          toastError(
            contact ? 'Contact could not be saved' : 'Contact could not be added',
            e instanceof ApiError ? e.problem.detail : undefined,
          )
        }
      })}
    >
      <div className="grid gap-4 md:grid-cols-6">
        <Input
          label="Honorific"
          placeholder="Col."
          className="md:col-span-1"
          {...register('honorific')}
        />
        <Input
          label="First name"
          className="md:col-span-3"
          {...register('first_name')}
          error={formState.errors.first_name?.message}
        />
        <Input label="Last name" className="md:col-span-2" {...register('last_name')} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Input label="Title" placeholder="Program Director" {...register('title')} />
        <Input
          label="Company"
          placeholder="Space Force"
          hint="Existing companies are matched by name."
          {...register('company_name')}
        />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Input label="Emails" hint="Separate with commas." {...register('emails')} />
        <Input label="Phones" hint="Separate with commas." {...register('phones')} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Input label="Location" {...register('location')} />
        <Input label="Tags" hint="Separate with commas." {...register('tags')} />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Select label="Relationship" {...register('relationship_type')}>
          {['client', 'partner', 'vendor', 'colleague', 'government', 'other'].map((r) => (
            <option key={r} value={r}>
              {r[0]!.toUpperCase() + r.slice(1)}
            </option>
          ))}
        </Select>
        <Select label="Visibility" {...register('visibility')}>
          <option value="team">Team</option>
          <option value="private">Private</option>
        </Select>
        <Input
          label="Cadence in days"
          type="number"
          min={1}
          max={365}
          hint="How often you expect to be in touch."
          {...register('cadence_days', { valueAsNumber: true })}
          error={formState.errors.cadence_days?.message}
        />
      </div>
      <div className="mt-2 flex justify-end gap-2">
        <Button variant="ghost" onClick={() => navigate(-1)}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" loading={busy}>
          {contact ? 'Save contact' : 'Add contact'}
        </Button>
      </div>
    </form>
  )
}

export function ContactCreatePage() {
  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-steel-100">Add contact</h1>
      <div className="mt-6">
        <Form />
      </div>
    </div>
  )
}

export function ContactEditPage() {
  const { id } = useParams()
  const { data, isLoading } = useContact(id)
  if (isLoading || !data) return <p className="text-sm text-steel-400">Loading</p>
  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-steel-100">Edit contact</h1>
      <div className="mt-6">
        <Form contact={data} />
      </div>
    </div>
  )
}
