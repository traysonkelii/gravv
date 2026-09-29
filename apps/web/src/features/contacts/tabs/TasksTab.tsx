import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Field'
import { toast, toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import type { Contact } from '@/features/contacts/api'
import { useCreateTask, useTasks } from '@/features/tasks/api'
import { TaskRow } from '@/features/tasks/TaskList'

export function TasksTab({ contact }: { contact: Contact }) {
  const open = useTasks({ status: 'open', contact_id: contact.id })
  const snoozed = useTasks({ status: 'snoozed', contact_id: contact.id })
  const done = useTasks({ status: 'done', contact_id: contact.id })
  const create = useCreateTask()
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  const [now] = useState(() => Date.now())
  const active = [
    ...(open.data?.pages.flatMap((p) => p.items) ?? []),
    ...(snoozed.data?.pages.flatMap((p) => p.items) ?? []),
  ]
  const overdue = active.filter((t) => t.due_at && new Date(t.due_at).getTime() < now)
  const upcoming = active.filter((t) => !overdue.includes(t))
  const finished = done.data?.pages.flatMap((p) => p.items) ?? []
  return (
    <div className="flex flex-col gap-6">
      <form
        className="flex flex-col gap-2 md:flex-row md:items-end"
        onSubmit={async (e) => {
          e.preventDefault()
          if (!title.trim()) return
          try {
            await create.mutateAsync({
              title: title.trim(),
              contact_id: contact.id,
              due_at: due ? new Date(due).toISOString() : null,
            })
            setTitle('')
            setDue('')
            toast('Task added')
          } catch (err) {
            toastError(
              'Task could not be added',
              err instanceof ApiError ? err.problem.detail : undefined,
            )
          }
        }}
      >
        <Input
          label="New task"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={200}
          className="flex-1"
        />
        <Input
          label="Due"
          type="datetime-local"
          value={due}
          onChange={(e) => setDue(e.target.value)}
          className="md:w-60"
        />
        <Button type="submit" variant="primary" disabled={!title.trim()} loading={create.isPending}>
          Add task
        </Button>
      </form>
      {overdue.length > 0 && (
        <section>
          <h2 className="text-md font-semibold text-rust-400">Overdue</h2>
          <ul>
            {overdue.map((t) => (
              <TaskRow key={t.id} task={t} showContact={false} />
            ))}
          </ul>
        </section>
      )}
      <section>
        <h2 className="text-md font-semibold text-steel-100">Open</h2>
        {upcoming.length ? (
          <ul>
            {upcoming.map((t) => (
              <TaskRow key={t.id} task={t} showContact={false} />
            ))}
          </ul>
        ) : (
          <p className="py-2 text-sm text-steel-400">No open tasks.</p>
        )}
      </section>
      {finished.length > 0 && (
        <section>
          <h2 className="text-md font-semibold text-steel-100">Done</h2>
          <ul>
            {finished.slice(0, 10).map((t) => (
              <TaskRow key={t.id} task={t} showContact={false} />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
