import { Mic, Square } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Field'
import { Icon } from '@/components/ui/Icon'
import { Sheet } from '@/components/ui/Sheet'
import { Tabs } from '@/components/ui/Tabs'
import { toastError } from '@/components/ui/Toast'
import { ApiError } from '@/lib/api/client'
import { useUiStore } from '@/lib/store'
import { useContact, type Contact } from '@/features/contacts/api'
import { ContactPicker } from '@/features/capture/ContactPicker'
import { LevelMeter } from '@/features/capture/LevelMeter'
import { newIdempotencyKey, useCreateTextCapture, useVoiceUpload } from '@/features/capture/api'
import { formatElapsed, useRecorder } from '@/features/capture/useRecorder'

function VoiceMode({ contact, onDone }: { contact: Contact | null; onDone: (id: string) => void }) {
  const rec = useRecorder()
  const upload = useVoiceUpload()
  const recording = rec.state === 'recording'
  if (rec.state === 'unsupported' || rec.state === 'denied') {
    return (
      <p className="text-base text-steel-300">
        {rec.state === 'denied'
          ? 'Microphone access was declined. Allow it in your browser settings, or use the Text tab.'
          : 'This browser cannot record audio. Use the Text tab instead.'}
      </p>
    )
  }
  return (
    <div className="flex flex-col items-start gap-4">
      <button
        type="button"
        onClick={() => (recording ? rec.stop() : rec.start())}
        aria-label={recording ? 'Stop recording' : 'Start recording'}
        aria-pressed={recording}
        className={`chamfer-br flex size-24 items-center justify-center ${recording ? 'bg-rust-500 text-steel-050' : 'bg-temper-500 text-steel-950'}`}
      >
        <Icon icon={recording ? Square : Mic} size={36} />
      </button>
      <div className="flex items-center gap-4">
        <span className="tnum font-display text-2xl font-bold text-steel-100">
          {formatElapsed(rec.elapsed)}
        </span>
        <LevelMeter levels={rec.levels} recording={recording} />
      </div>
      <p className="text-sm text-steel-400">
        {recording
          ? 'Tap the square to stop. Recordings stop at ten minutes.'
          : rec.blob
            ? 'Recording ready.'
            : 'Tap to start. Say who you met and what to remember.'}
      </p>
      {rec.blob && (
        <div className="flex gap-2">
          <Button variant="ghost" onClick={rec.reset}>
            Discard
          </Button>
          <Button
            variant="primary"
            loading={upload.isPending}
            loadingLabel="Uploading..."
            onClick={async () => {
              try {
                const cap = await upload.mutateAsync({
                  blob: rec.blob!,
                  contentType: rec.contentType,
                  contactId: contact?.id,
                  durationSeconds: rec.elapsed,
                })
                onDone(cap.id)
              } catch (e) {
                toastError(
                  'Recording could not be uploaded',
                  e instanceof ApiError ? e.problem.detail : (e as Error).message,
                )
              }
            }}
          >
            Use recording
          </Button>
        </div>
      )}
    </div>
  )
}

function TextMode({ contact, onDone }: { contact: Contact | null; onDone: (id: string) => void }) {
  const [text, setText] = useState('')
  const create = useCreateTextCapture()
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={async (e) => {
        e.preventDefault()
        if (!text.trim()) return
        try {
          const cap = await create.mutateAsync({
            text: text.trim(),
            contact_id: contact?.id ?? null,
            idempotency_key: newIdempotencyKey(),
          })
          setText('')
          onDone(cap.id)
        } catch (err) {
          toastError(
            'Note could not be sent',
            err instanceof ApiError ? err.problem.detail : undefined,
          )
        }
      }}
    >
      <Textarea
        label="What happened"
        rows={6}
        placeholder="Met the Colonel, he loves competitive pinball, remind me to call the program officers next Tuesday"
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={20000}
      />
      <div className="flex justify-end">
        <Button
          type="submit"
          variant="primary"
          disabled={!text.trim()}
          loading={create.isPending}
          loadingLabel="Sending..."
        >
          Extract note
        </Button>
      </div>
    </form>
  )
}

export function CaptureSheet() {
  const open = useUiStore((s) => s.captureOpen)
  const preselected = useUiStore((s) => s.captureContactId)
  const close = useUiStore((s) => s.closeCapture)
  const navigate = useNavigate()
  const [mode, setMode] = useState<'voice' | 'text'>('voice')
  const [picked, setPicked] = useState<Contact | null>(null)
  const { data: preselectedContact } = useContact(preselected ?? undefined)
  const contact = picked ?? (preselected ? (preselectedContact ?? null) : null)
  const done = (id: string) => {
    close()
    setPicked(null)
    navigate(`/app/captures/${id}`)
  }
  return (
    <Sheet open={open} title="Capture" onClose={close}>
      <div className="flex flex-col gap-4">
        <ContactPicker value={contact} onChange={setPicked} label="Who is this about (optional)" />
        <Tabs
          tabs={[
            { key: 'voice', label: 'Voice' },
            { key: 'text', label: 'Text' },
          ]}
          value={mode}
          onChange={(k) => setMode(k as 'voice' | 'text')}
          ariaLabel="Capture mode"
        />
        {open &&
          (mode === 'voice' ? (
            <VoiceMode contact={contact} onDone={done} />
          ) : (
            <TextMode contact={contact} onDone={done} />
          ))}
      </div>
    </Sheet>
  )
}
