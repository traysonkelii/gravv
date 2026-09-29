import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force'
import { quadtree, type Quadtree } from 'd3-quadtree'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { GraphEdge, GraphNode } from '@/features/network/api'

export type SimNode = SimulationNodeDatum & GraphNode & { r: number }
export type SimLink = SimulationLinkDatum<SimNode> & { strength: number; kind: string; id: string }

export function nodeRadius(n: GraphNode): number {
  if (n.kind === 'me') return 22
  return (16 + (n.gravity_score / 100) * 20) / 2
}

/* Runs the d3-force simulation off the render path and exposes positions through a ref plus a tick counter. */
export function useForceGraph(nodes: GraphNode[], edges: GraphEdge[]) {
  const simNodes = useRef<SimNode[]>([])
  const simLinks = useRef<SimLink[]>([])
  const tree = useRef<Quadtree<SimNode> | null>(null)
  const [tick, setTick] = useState(0)
  const key = useMemo(
    () => nodes.map((n) => n.id).join(',') + '|' + edges.map((e) => e.id).join(','),
    [nodes, edges],
  )

  useEffect(() => {
    const previous = new Map(simNodes.current.map((n) => [n.id, n]))
    const sn: SimNode[] = nodes.map((n) => {
      const prev = previous.get(n.id)
      return {
        ...n,
        r: nodeRadius(n),
        x: prev?.x,
        y: prev?.y,
        vx: 0,
        vy: 0,
        fx: n.kind === 'me' ? 0 : undefined,
        fy: n.kind === 'me' ? 0 : undefined,
      }
    })
    const byId = new Map(sn.map((n) => [n.id, n]))
    const sl: SimLink[] = edges
      .filter((e) => byId.has(e.source) && byId.has(e.target))
      .map((e) => ({
        id: e.id,
        source: byId.get(e.source)!,
        target: byId.get(e.target)!,
        strength: e.strength,
        kind: e.kind,
      }))
    simNodes.current = sn
    simLinks.current = sl
    const sim = forceSimulation(sn)
      .force('charge', forceManyBody().strength(-260))
      .force(
        'link',
        forceLink<SimNode, SimLink>(sl)
          .id((d) => d.id)
          .distance((l) => 80 + (100 - l.strength) * 1.6)
          .strength(0.6),
      )
      .force('center', forceCenter(0, 0))
      .force(
        'collide',
        forceCollide<SimNode>((d) => d.r + 10),
      )
      .alphaDecay(0.035)
      .on('tick', () => {
        tree.current = quadtree<SimNode>()
          .x((d) => d.x ?? 0)
          .y((d) => d.y ?? 0)
          .addAll(sn)
        setTick((t) => t + 1)
      })
    return () => {
      sim.stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return { simNodes, simLinks, tree, tick }
}
