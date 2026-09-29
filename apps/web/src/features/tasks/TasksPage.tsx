import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input } from '@/components/ui/Field'
import { ListSkeleton } from '@/components/ui/Skeleton'
import { Tabs } from '@/components/ui/Tabs'
import { toast, toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import { useCreateTask, useTasks, type Task } from '@/features/tasks/api'
import { TaskRow } from '@/features/tasks/TaskList'

type View = 'due' | 'overdue' | 'done'

export function TasksPage() {
  const [view, setView] = useState<View>('due')
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  const create = useCreateTask()
  const open = useTasks({ status: 'open', assignee: 'me' })
  const snoozed = useTasks({ status: 'snoozed', assignee: 'me' })
  const done = useTasks({ status: 'done', assignee: 'me' })
  const [now] = useState(() => Date.now())
  const openItems: Task[] = [
    ...(open.data?.pages.flatMap((p) => p.items) ?? []),
    ...(snoozed.data?.pages.flatMap((p) => p.items) ?? []),
  ]
  const overdue = openItems.filter((t) => t.due_at && new Date(t.due_at).getTime() < now)
  const dueItems = openItems.filter((t) => !overdue.includes(t))
  const doneItems = done.data?.pages.flatMap((p) => p.items) ?? []
  const items = view === 'due' ? dueItems : view === 'overdue' ? overdue : doneItems
  const loading = open.isLoading || done.isLoading
  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-steel-100">Tasks</h1>
      <form
        className="mt-4 flex flex-col gap-2 md:flex-row md:items-end"
        onSubmit={async (e) => {
          e.preventDefault()
          if (!title.trim()) return
          try {
            await create.mutateAsync({
              title: title.trim(),
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
      <div className="mt-6">
        <Tabs
          tabs={[
            { key: 'due', label: `Due (${dueItems.length})` },
            { key: 'overdue', label: `Overdue (${overdue.length})` },
            { key: 'done', label: 'Done' },
          ]}
          value={view}
          onChange={(k) => setView(k as View)}
          ariaLabel="Task views"
        />
      </div>
      <div className="mt-2">
        {loading ? (
          <ListSkeleton />
        ) : items.length === 0 ? (
          <EmptyState
            title={view === 'done' ? 'Nothing completed yet' : 'Nothing here'}
            body={
              view === 'overdue'
                ? 'No overdue tasks. Good.'
                : 'Add a task above or confirm a capture that mentions a follow-up.'
            }
          />
        ) : (
          <ul>
            {items.map((t) => (
              <TaskRow key={t.id} task={t} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
