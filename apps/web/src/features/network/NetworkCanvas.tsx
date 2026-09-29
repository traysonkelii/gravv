import { zoom, zoomIdentity, type ZoomTransform } from 'd3-zoom'
import { select } from 'd3-selection'
import { useEffect, useRef, useState } from 'react'
import type { GraphEdge, GraphNode } from '@/features/network/api'
import { useForceGraph, type SimNode } from '@/features/network/useForceGraph'

type Props = {
  nodes: GraphNode[]
  edges: GraphEdge[]
  selectedId: string | null
  highlightPath: string[] | null
  onSelect: (id: string | null) => void
  resetSignal: number
  exportSignal: number
}

const bandVar = (band: string) => `--color-band-${band}`

/* Full-bleed canvas: 32px machinist grid, square nodes sized by score, brightness by band, quadtree hit testing,
   pan and zoom, keyboard selection, and a hidden node list for screen readers. */
export function NetworkCanvas({
  nodes,
  edges,
  selectedId,
  highlightPath,
  onSelect,
  resetSignal,
  exportSignal,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const transform = useRef<ZoomTransform>(zoomIdentity)
  const [hoverId, setHoverId] = useState<string | null>(null)
  const { simNodes, simLinks, tree, tick } = useForceGraph(nodes, edges)
  const [size, setSize] = useState({ w: 800, h: 600 })

  useEffect(() => {
    const el = canvasRef.current?.parentElement
    if (!el) return
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }))
    ro.observe(el)
    setSize({ w: el.clientWidth, h: el.clientHeight })
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const z = zoom<HTMLCanvasElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', (e) => {
        transform.current = e.transform
        draw()
      })
    select(canvas).call(z)
    if (resetSignal) z.transform(select(canvas), zoomIdentity)
    return () => {
      select(canvas).on('.zoom', null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetSignal])

  const css = (name: string) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim()

  function draw() {
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    if (canvas.width !== size.w * dpr || canvas.height !== size.h * dpr) {
      canvas.width = size.w * dpr
      canvas.height = size.h * dpr
    }
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.fillStyle = css('--color-steel-950')
    ctx.fillRect(0, 0, size.w, size.h)
    const t = transform.current
    const grid = 32 * t.k
    ctx.strokeStyle = css('--color-steel-800')
    ctx.lineWidth = 1
    ctx.beginPath()
    for (let x = ((t.x % grid) + grid) % grid; x < size.w; x += grid) {
      ctx.moveTo(x, 0)
      ctx.lineTo(x, size.h)
    }
    for (let y = ((t.y % grid) + grid) % grid; y < size.h; y += grid) {
      ctx.moveTo(0, y)
      ctx.lineTo(size.w, y)
    }
    ctx.stroke()

    ctx.save()
    ctx.translate(size.w / 2 + t.x, size.h / 2 + t.y)
    ctx.scale(t.k, t.k)
    const path = highlightPath ? new Set(highlightPath) : null
    const onPath = (a: string, b: string) => {
      if (!highlightPath) return false
      const i = highlightPath.indexOf(a)
      const j = highlightPath.indexOf(b)
      return i >= 0 && j >= 0 && Math.abs(i - j) === 1
    }
    for (const l of simLinks.current) {
      const s = l.source as SimNode
      const d = l.target as SimNode
      const band = d.kind === 'me' ? s.band : d.band
      const active = onPath(s.id, d.id)
      ctx.globalAlpha = path && !active ? 0.15 : 0.6
      ctx.strokeStyle = active ? css('--color-temper-500') : css(bandVar(band))
      ctx.lineWidth = active ? 3 : 1 + (l.strength / 100) * 2
      ctx.beginPath()
      ctx.moveTo(s.x ?? 0, s.y ?? 0)
      ctx.lineTo(d.x ?? 0, d.y ?? 0)
      ctx.stroke()
    }
    ctx.globalAlpha = 1
    for (const n of simNodes.current) {
      const x = (n.x ?? 0) - n.r
      const y = (n.y ?? 0) - n.r
      const dim = path && !path.has(n.id)
      ctx.globalAlpha = dim ? 0.35 : 1
      ctx.fillStyle = n.kind === 'me' ? css('--color-steel-700') : css(bandVar(n.band))
      ctx.fillRect(x, y, n.r * 2, n.r * 2)
      if (n.kind === 'me' || n.id === selectedId) {
        ctx.strokeStyle = css('--color-temper-500')
        ctx.lineWidth = n.id === selectedId ? 2 : 1
        ctx.strokeRect(x, y, n.r * 2, n.r * 2)
      }
      if (n.kind === 'me') {
        ctx.fillStyle = css('--color-steel-100')
        ctx.font = `700 14px "Big Shoulders Variable", "Big Shoulders", sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(n.initials, n.x ?? 0, n.y ?? 0)
      }
      if (n.id === hoverId || n.id === selectedId || path?.has(n.id)) {
        ctx.fillStyle = css('--color-steel-200')
        ctx.font = `12px "IBM Plex Sans", sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        ctx.fillText(n.display_name, n.x ?? 0, (n.y ?? 0) + n.r + 4)
      }
    }
    ctx.restore()
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(draw, [tick, size, selectedId, hoverId, highlightPath])

  const hit = (clientX: number, clientY: number): SimNode | null => {
    const canvas = canvasRef.current
    if (!canvas || !tree.current) return null
    const rect = canvas.getBoundingClientRect()
    const t = transform.current
    const x = (clientX - rect.left - size.w / 2 - t.x) / t.k
    const y = (clientY - rect.top - size.h / 2 - t.y) / t.k
    const found = tree.current.find(x, y, 30)
    if (!found) return null
    return Math.abs((found.x ?? 0) - x) <= found.r + 4 &&
      Math.abs((found.y ?? 0) - y) <= found.r + 4
      ? found
      : null
  }

  useEffect(() => {
    if (!exportSignal) return
    const canvas = canvasRef.current
    if (!canvas) return
    const a = document.createElement('a')
    a.href = canvas.toDataURL('image/png')
    a.download = 'gravv-network.png'
    a.click()
  }, [exportSignal])

  const onKey = (e: React.KeyboardEvent<HTMLCanvasElement>) => {
    const list = simNodes.current
    if (list.length === 0) return
    const idx = list.findIndex((n) => n.id === selectedId)
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault()
      onSelect(list[(idx + 1) % list.length]!.id)
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault()
      onSelect(list[(idx - 1 + list.length) % list.length]!.id)
    } else if (e.key === 'Escape') {
      onSelect(null)
    }
  }

  return (
    <div className="relative h-full w-full">
      <canvas
        ref={canvasRef}
        style={{ width: size.w, height: size.h }}
        className="block cursor-grab touch-none"
        tabIndex={0}
        role="img"
        aria-label={`Network of ${nodes.length - 1} contacts. Use the arrow keys to move between nodes, or the list below.`}
        onMouseMove={(e) => setHoverId(hit(e.clientX, e.clientY)?.id ?? null)}
        onClick={(e) => onSelect(hit(e.clientX, e.clientY)?.id ?? null)}
        onKeyDown={onKey}
      />
      <ul className="sr-only" aria-label="Network nodes">
        {nodes.map((n) => (
          <li key={n.id}>
            <button type="button" onClick={() => onSelect(n.id)}>
              {n.display_name}
              {n.kind === 'contact'
                ? `, ${n.company ?? 'no company'}, gravity ${n.gravity_score} ${n.band}`
                : ''}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
