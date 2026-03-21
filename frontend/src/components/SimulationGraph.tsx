import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from 'd3-force'
import { useEffect, useRef, useState } from 'react'
import type { Message, NetworkEdge, PersonaStance } from '../types/models'

interface GraphNode extends PersonaStance {
  x: number
  y: number
}

interface SimulationGraphProps {
  roster: PersonaStance[]
  networkEdges: NetworkEdge[]
  messages: Message[]
}

const WIDTH = 820
const HEIGHT = 560

export function SimulationGraph({ roster, networkEdges, messages }: SimulationGraphProps) {
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const layoutSignatureRef = useRef('')
  const positionMapRef = useRef<Record<string, { x: number; y: number }>>({})
  const lastPersonaMessage = [...messages].reverse().find((message) => message.role === 'persona')

  useEffect(() => {
    const signature = JSON.stringify({
      ids: roster.map((entry) => entry.persona_id).sort(),
      edges: networkEdges.map((edge) => `${edge.source_id}:${edge.target_id}`).sort(),
    })

    if (layoutSignatureRef.current === signature && Object.keys(positionMapRef.current).length > 0) {
      const nextNodes = roster.map((entry) => ({
        ...entry,
        x: positionMapRef.current[entry.persona_id]?.x ?? WIDTH / 2,
        y: positionMapRef.current[entry.persona_id]?.y ?? HEIGHT / 2,
      }))
      const frame = window.requestAnimationFrame(() => {
        setNodes(nextNodes)
      })
      return () => {
        window.cancelAnimationFrame(frame)
      }
    }

    const seededNodes: GraphNode[] = roster.map((entry, index) => {
      const angle = (Math.PI * 2 * index) / Math.max(roster.length, 1)
      return {
        ...entry,
        x: WIDTH / 2 + Math.cos(angle) * 180,
        y: HEIGHT / 2 + Math.sin(angle) * 160,
      }
    })

    const simulation = forceSimulation(seededNodes)
      .force(
        'link',
        forceLink(
          networkEdges.map((edge) => ({
            source: edge.source_id,
            target: edge.target_id,
          })),
        )
          .id((node) => (node as GraphNode).persona_id)
          .distance(155)
          .strength(0.9),
      )
      .force('charge', forceManyBody().strength(-310))
      .force('center', forceCenter(WIDTH / 2, HEIGHT / 2))
      .force(
        'collide',
        forceCollide().radius((node) => radiusForConfidence((node as GraphNode).confidence) + 22),
      )

    for (let step = 0; step < 220; step += 1) {
      simulation.tick()
    }
    simulation.stop()

    layoutSignatureRef.current = signature
    positionMapRef.current = Object.fromEntries(
      seededNodes.map((node) => [node.persona_id, { x: node.x, y: node.y }]),
    )
    const frame = window.requestAnimationFrame(() => {
      setNodes(seededNodes)
    })
    return () => {
      window.cancelAnimationFrame(frame)
    }
  }, [networkEdges, roster])

  return (
    <div className="graph-shell graph-frame">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="simulation-graph" role="img" aria-label="Agent interaction graph">
        <desc>An interaction graph showing personas, their stances, and recent influence links.</desc>
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="6" result="blurred" />
            <feMerge>
              <feMergeNode in="blurred" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {networkEdges.map((edge) => {
          const source = nodes.find((node) => node.persona_id === edge.source_id)
          const target = nodes.find((node) => node.persona_id === edge.target_id)
          if (!source || !target) {
            return null
          }
          return (
            <line
              key={`${edge.source_id}-${edge.target_id}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              className="graph-edge"
            />
          )
        })}

        {nodes.map((node) => {
          const activeSpeaker = lastPersonaMessage?.author_id === node.persona_id
          const radius = radiusForConfidence(node.confidence)
          return (
            <g key={node.persona_id} transform={`translate(${node.x}, ${node.y})`}>
              {activeSpeaker ? (
                <circle r={radius + 16} className="graph-node-aura" filter="url(#glow)" />
              ) : null}
              <circle r={radius} fill={colorForStance(node.stance)} className="graph-node-circle" />
              <text y="6" textAnchor="middle" className="graph-node-emoji">
                {node.avatar_emoji}
              </text>
              <text y={radius + 18} textAnchor="middle" className="graph-node-label graph-node-meta">
                {node.persona_name}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

function radiusForConfidence(confidence: number) {
  return 24 + confidence * 18
}

function colorForStance(stance: number) {
  if (stance >= 0.18) {
    return '#295e49'
  }
  if (stance <= -0.18) {
    return '#b54f35'
  }
  return '#bc8c2f'
}
