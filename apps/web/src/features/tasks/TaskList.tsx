import { useState } from 'react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/Button'
import { Checkbox } from '@/components/ui/Checkbox'
import { toast, toastError } from '@/components/ui/Toast'
import { dueLabel, formatDate } from '@/lib/format'
import { useCompleteTask, useSnoozeTask, type Task } from '@/features/tasks/api'

function snoozeUntil(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  d.setHours(9, 0, 0, 0)
  return d.toISOString()
}

export function TaskRow({ task, showContact = true }: { task: Task; showContact?: boolean }) {
  const complete = useCompleteTask()
  const snooze = useSnoozeTask()
  const [now] = useState(() => Date.now())
  const overdue = task.status === 'open' && task.due_at && Date.parse(task.due_at) < now
  const done = task.status === 'done'
  return (
    <li className="flex flex-col gap-2 border-b border-steel-600 py-3 md:flex-row md:items-center">
      <Checkbox
        label={task.title}
        description={[
          showContact && task.contact_name ? task.contact_name : null,
          done
            ? `done ${formatDate(task.completed_at)}`
            : task.status === 'snoozed'
              ? `snoozed until ${formatDate(task.snoozed_until)}`
              : dueLabel(task.due_at),
          task.priority === 1 ? 'high priority' : null,
        ]
          .filter(Boolean)
          .join(', ')}
        checked={done}
        disabled={done}
        onChange={() =>
          complete.mutate(task.id, {
            onSuccess: () => toast('Task completed'),
            onError: () => toastError('Task could not be completed'),
          })
        }
        className={`flex-1 ${overdue ? 'text-rust-400' : ''}`}
      />
      {!done && (
        <div className="flex shrink-0 gap-1 md:pl-4">
          <Button
            variant="ghost"
            onClick={() => snooze.mutate({ id: task.id, until: snoozeUntil(1) })}
          >
            Snooze 1 day
          </Button>
          <Button
            variant="ghost"
            onClick={() => snooze.mutate({ id: task.id, until: snoozeUntil(7) })}
          >
            Snooze 1 week
          </Button>
          {showContact && task.contact_id && (
            <Link
              to={`/app/contacts/${task.contact_id}`}
              className="inline-flex h-11 items-center px-3 text-sm text-steel-300 hover:text-steel-100 md:h-10"
            >
              Open
            </Link>
          )}
        </div>
      )}
    </li>
  )
}
