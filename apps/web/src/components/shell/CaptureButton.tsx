import { Mic, Square } from 'lucide-react'
import { Icon } from '@/components/ui/Icon'
import { copy } from '@/lib/copy'
import { useUiStore } from '@/lib/store'

export function CaptureButton({
  withLabel = false,
  recording = false,
}: {
  withLabel?: boolean
  recording?: boolean
}) {
  const open = useUiStore((s) => s.openCapture)
  return (
    <button
      type="button"
      onClick={() => open()}
      aria-label={copy.nav.capture}
      className={`chamfer-br inline-flex h-14 items-center justify-center gap-2 text-sm font-medium ${
        withLabel ? 'w-full' : 'w-14'
      } ${recording ? 'bg-rust-500 text-steel-050' : 'bg-temper-500 text-steel-950'}`}
    >
      <Icon icon={recording ? Square : Mic} size={22} />
      {withLabel && <span>{copy.nav.capture}</span>}
    </button>
  )
}
