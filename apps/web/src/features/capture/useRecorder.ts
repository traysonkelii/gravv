import { useCallback, useEffect, useRef, useState } from 'react'

export type RecorderState = 'idle' | 'recording' | 'stopped' | 'denied' | 'unsupported'
const MAX_SECONDS = 600
const BARS = 32

function pickMime(): { mime: string; contentType: 'audio/webm' | 'audio/mp4' } | null {
  if (typeof MediaRecorder === 'undefined') return null
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus'))
    return { mime: 'audio/webm;codecs=opus', contentType: 'audio/webm' }
  if (MediaRecorder.isTypeSupported('audio/webm'))
    return { mime: 'audio/webm', contentType: 'audio/webm' }
  if (MediaRecorder.isTypeSupported('audio/mp4'))
    return { mime: 'audio/mp4', contentType: 'audio/mp4' }
  return null
}

/* Tap to start, tap to stop. Hard stop at ten minutes. Exposes 32 level values for the meter. */
export function useRecorder() {
  const [state, setState] = useState<RecorderState>(() => (pickMime() ? 'idle' : 'unsupported'))
  const [elapsed, setElapsed] = useState(0)
  const [levels, setLevels] = useState<number[]>(() => Array(BARS).fill(0))
  const [blob, setBlob] = useState<Blob | null>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const stream = useRef<MediaStream | null>(null)
  const audioCtx = useRef<AudioContext | null>(null)
  const raf = useRef<number | null>(null)
  const timer = useRef<number | null>(null)
  const startedAt = useRef(0)
  const [contentType, setContentType] = useState<'audio/webm' | 'audio/mp4'>('audio/webm')

  const cleanup = useCallback(() => {
    if (raf.current) cancelAnimationFrame(raf.current)
    if (timer.current) window.clearInterval(timer.current)
    stream.current?.getTracks().forEach((t) => t.stop())
    void audioCtx.current?.close()
    raf.current = null
    timer.current = null
    stream.current = null
    audioCtx.current = null
  }, [])

  const stop = useCallback(() => {
    const r = recorder.current
    if (r && r.state !== 'inactive') r.stop()
  }, [])

  const start = useCallback(async () => {
    const picked = pickMime()
    if (!picked) return setState('unsupported')
    let media: MediaStream
    try {
      media = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setState('denied')
      return
    }
    stream.current = media
    setContentType(picked.contentType)
    chunks.current = []
    setBlob(null)
    const r = new MediaRecorder(media, { mimeType: picked.mime, audioBitsPerSecond: 32_000 })
    recorder.current = r
    r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data)
    r.onstop = () => {
      setBlob(new Blob(chunks.current, { type: picked.contentType }))
      setState('stopped')
      cleanup()
    }
    const ctx = new AudioContext()
    audioCtx.current = ctx
    const source = ctx.createMediaStreamSource(media)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 64
    source.connect(analyser)
    const data = new Uint8Array(analyser.frequencyBinCount)
    const tick = () => {
      analyser.getByteFrequencyData(data)
      setLevels(Array.from({ length: BARS }, (_, i) => (data[i] ?? 0) / 255))
      raf.current = requestAnimationFrame(tick)
    }
    tick()
    startedAt.current = Date.now()
    setElapsed(0)
    timer.current = window.setInterval(() => {
      const secs = Math.floor((Date.now() - startedAt.current) / 1000)
      setElapsed(secs)
      if (secs >= MAX_SECONDS) stop()
    }, 250)
    r.start(1000)
    setState('recording')
  }, [cleanup, stop])

  const reset = useCallback(() => {
    cleanup()
    setBlob(null)
    setElapsed(0)
    setLevels(Array(BARS).fill(0))
    setState(pickMime() ? 'idle' : 'unsupported')
  }, [cleanup])

  useEffect(() => cleanup, [cleanup])

  return { state, elapsed, levels, blob, contentType, start, stop, reset }
}

export function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}
