import { useCallback, useMemo, useState } from 'react'
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { nodeTypes } from './nodes'
import { NODE_DEFAULTS } from './nodes/defaults'
import { NodePalette } from './components/NodePalette'
import { NodeConfigPanel } from './components/NodeConfigPanel'
import { EdgeConfigPanel } from './components/EdgeConfigPanel'
import { SimControls } from './components/SimControls'
import { ResultsPanel } from './components/ResultsPanel'
import { Toolbar } from './components/Toolbar'
import { simulate } from './api'
import type { SimNode, SimEdge, NodeData, SimulateResponse, BurstConfig, ArchPreset, PresetNode, OutageEntry } from './types'
import type { NodeTypeName } from './nodes'

const VALID_TYPES = new Set(Object.keys(nodeTypes))

const initialNodes: SimNode[] = [
  {
    id: 'lb',
    type: 'load_balancer',
    position: { x: 80, y: 200 },
    data: { ...NODE_DEFAULTS.load_balancer, name: 'Load Balancer' },
  },
  {
    id: 'app',
    type: 'app_server',
    position: { x: 360, y: 100 },
    data: { ...NODE_DEFAULTS.app_server, name: 'App Server' },
  },
  {
    id: 'db',
    type: 'database',
    position: { x: 640, y: 200 },
    data: { ...NODE_DEFAULTS.database, name: 'Database' },
  },
]

const initialEdges: SimEdge[] = [
  { id: 'e-lb-app', source: 'lb', target: 'app' },
  { id: 'e-app-db', source: 'app', target: 'db' },
]

// ─── helpers ────────────────────────────────────────────────────────────────

/** Returns the id of the node with no incoming edges (in-degree 0). */
function detectEntryNode(nodes: SimNode[], edges: SimEdge[]): string | null {
  const hasIncoming = new Set(edges.map((e) => e.target))
  const entry = nodes.find((n) => !hasIncoming.has(n.id))
  return entry?.id ?? null
}

/** Build the routing dict expected by the backend for all multi-output nodes. */
function buildRouting(
  nodes: SimNode[],
  edges: SimEdge[],
): Record<string, { strategy: string; weights?: Record<string, number> }> {
  const outDegree: Record<string, number> = {}
  for (const e of edges) outDegree[e.source] = (outDegree[e.source] ?? 0) + 1

  const routing: Record<string, { strategy: string; weights?: Record<string, number> }> = {}
  for (const n of nodes) {
    if ((outDegree[n.id] ?? 0) < 2) continue
    const strategy = (n.data.routing_strategy as string) ?? 'first'
    if (strategy === 'first') continue  // default — no need to send
    const entry: { strategy: string; weights?: Record<string, number> } = { strategy }
    if (strategy === 'weighted' && n.data.routing_weights) {
      entry.weights = n.data.routing_weights as Record<string, number>
    }
    routing[n.id] = entry
  }
  return routing
}

/** Infer a visual node type from preset node fields. */
function guessNodeType(
  node: PresetNode,
  routing: Record<string, { strategy: string }>,
): NodeTypeName {
  const id   = node.id.toLowerCase()
  const name = node.name.toLowerCase()

  if (id.includes('cdn') || name.includes('cdn') || name.includes('edge'))
    return 'cdn'
  if (id.includes('pay') || name.includes('payment'))
    return 'payment_gateway'
  if (id.includes('queue') || id.includes('mq') || name.includes('queue'))
    return 'message_queue'
  if ((node.hit_rate ?? 0) > 0 || id.includes('cache') || name.includes('cache'))
    return 'cache'
  if (id.includes('db') || name.includes('database') || name.includes(' db'))
    return 'database'
  if (
    node.id in routing ||
    id === 'lb' || id.startsWith('lb_') ||
    name.includes('load balancer') ||
    name.includes('gateway')
  )
    return 'load_balancer'
  return 'app_server'
}

/** BFS-based left-to-right layout. Returns id → {x, y}. */
function computeLayout(
  nodes: PresetNode[],
  edges: [string, string][],
  entryId: string,
): Record<string, { x: number; y: number }> {
  const adj: Record<string, string[]> = Object.fromEntries(nodes.map((n) => [n.id, []]))
  for (const [src, tgt] of edges) {
    adj[src]?.push(tgt)
  }

  // BFS to assign depth levels
  const levels: Record<string, number> = {}
  const queue = [entryId]
  levels[entryId] = 0
  while (queue.length > 0) {
    const cur = queue.shift()!
    for (const next of adj[cur] ?? []) {
      if (levels[next] === undefined) {
        levels[next] = levels[cur] + 1
        queue.push(next)
      }
    }
  }
  // Disconnected nodes go after the deepest level
  const maxLevel = Math.max(0, ...Object.values(levels))
  for (const n of nodes) {
    if (levels[n.id] === undefined) levels[n.id] = maxLevel + 1
  }

  // Group by level
  const byLevel: Record<number, string[]> = {}
  for (const [id, lv] of Object.entries(levels)) {
    ;(byLevel[lv] ??= []).push(id)
  }

  // Assign x/y — center each column vertically
  const X_GAP = 240
  const Y_GAP = 130
  const positions: Record<string, { x: number; y: number }> = {}
  for (const [lvStr, ids] of Object.entries(byLevel)) {
    const lv = Number(lvStr)
    const totalH = (ids.length - 1) * Y_GAP
    ids.forEach((id, i) => {
      positions[id] = { x: 80 + lv * X_GAP, y: 200 - totalH / 2 + i * Y_GAP }
    })
  }
  return positions
}

// ─── component ──────────────────────────────────────────────────────────────

export default function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const { screenToFlowPosition, fitView } = useReactFlow()

  const [simResult, setSimResult] = useState<SimulateResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [simError, setSimError] = useState<string | null>(null)

  const selectedNode = nodes.find((n) => n.selected) ?? null
  const selectedEdge = edges.find((e) => e.selected) ?? null

  // Derive is_entry for each node without mutating state
  const displayNodes = useMemo(() => {
    const hasIncoming = new Set(edges.map((e) => e.target))
    return nodes.map((n) => ({
      ...n,
      data: { ...n.data, is_entry: !hasIncoming.has(n.id) },
    }))
  }, [nodes, edges])

  // Add latency labels to edges that have link latency configured
  const displayEdges = useMemo(() =>
    edges.map((e) => {
      const ms = e.data?.latency_ms
      if (!ms) return e
      return {
        ...e,
        label: `${ms}ms`,
        labelStyle: { fill: '#94a3b8', fontSize: 10 },
        labelBgStyle: { fill: '#1e293b', fillOpacity: 0.9 },
        labelBgPadding: [4, 2] as [number, number],
        labelBgBorderRadius: 3,
      }
    }),
    [edges],
  )

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges],
  )

  const onUpdateNode = useCallback(
    (id: string, patch: Partial<NodeData>) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n)),
      )
    },
    [setNodes],
  )

  const onUpdateEdge = useCallback(
    (id: string, patch: { latency_ms: number | null }) => {
      setEdges((eds) =>
        eds.map((e) => (e.id === id ? { ...e, data: { ...e.data, ...patch } } : e)),
      )
    },
    [setEdges],
  )

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const nodeType = e.dataTransfer.getData('application/reactflow')
      if (!nodeType || !VALID_TYPES.has(nodeType)) return

      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
      const id = crypto.randomUUID().slice(0, 8)

      const newNode: SimNode = {
        id,
        type: nodeType,
        position,
        data: { ...NODE_DEFAULTS[nodeType as NodeTypeName] },
      }

      setNodes((nds) => [...nds, newNode])
    },
    [screenToFlowPosition, setNodes],
  )

  const onRun = useCallback(
    async (params: {
      rate: number
      duration: number
      seed: number
      burst: BurstConfig | null
    }) => {
      setSimError(null)

      const entryId = detectEntryNode(nodes, edges)
      if (!entryId) {
        setSimError('Cannot detect entry node. Make sure one node has no incoming connections.')
        return
      }
      if (nodes.length === 0) {
        setSimError('Add at least one node to the canvas before running.')
        return
      }

      if (nodes.length > 1) {
        const connected = new Set([...edges.map((e) => e.source), ...edges.map((e) => e.target)])
        const stranded = nodes.filter((n) => !connected.has(n.id))
        if (stranded.length > 0) {
          setSimError(
            `Disconnected node${stranded.length > 1 ? 's' : ''}: ${stranded.map((n) => n.data.name).join(', ')}`,
          )
          return
        }
      }

      setRunning(true)
      try {
        const result = await simulate({
          nodes: nodes.map((n) => ({
            id: n.id,
            name: n.data.name,
            node_type: n.data.node_type,
            capacity: n.data.capacity,
            mean_processing_time: n.data.mean_processing_time,
            std_processing_time: n.data.std_processing_time,
            failure_rate: n.data.failure_rate,
            hit_rate: n.data.hit_rate,
            timeout: n.data.timeout,
            processing_profiles: n.data.processing_profiles,
            fan_out: n.data.fan_out ?? false,
            outages: (n.data.outages as OutageEntry[] | undefined) ?? [],
          })),
          edges: edges.map((e) => [e.source, e.target]),
          entry_node_id: entryId,
          routing: buildRouting(nodes, edges),
          link_latency: edges
            .filter((e) => e.data?.latency_ms != null && e.data.latency_ms > 0)
            .map((e) => [e.source, e.target, e.data!.latency_ms! / 1000] as [string, string, number]),
          rate: params.rate,
          duration: params.duration,
          seed: params.seed,
          burst: params.burst,
        })

        setSimResult(result)

        // Stamp avg_utilization onto each node for the canvas overlay
        const nodeMetrics = result.summary.node_metrics
        setNodes((nds) =>
          nds.map((n) => ({
            ...n,
            data: {
              ...n.data,
              avg_utilization: nodeMetrics[n.id]?.avg_utilization ?? undefined,
            },
          })),
        )
      } catch (err) {
        setSimError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setRunning(false)
      }
    },
    [nodes, edges, setNodes],
  )

  const loadPreset = useCallback(
    (preset: ArchPreset) => {
      const routing = preset.routing ?? {}
      const positions = computeLayout(preset.nodes, preset.edges, preset.entry_node_id)

      const newNodes: SimNode[] = preset.nodes.map((pn) => {
        const type = guessNodeType(pn, routing)
        const defaults = NODE_DEFAULTS[type]
        return {
          id: pn.id,
          type,
          position: positions[pn.id] ?? { x: 0, y: 0 },
          data: {
            ...defaults,
            name: pn.name,
            capacity: pn.capacity,
            mean_processing_time: pn.mean_processing_time,
            std_processing_time: pn.std_processing_time,
            failure_rate: pn.failure_rate,
            hit_rate: pn.hit_rate ?? defaults.hit_rate,
            timeout: pn.timeout ?? null,
            processing_profiles: pn.processing_profiles ?? {},
            routing_strategy: routing[pn.id]?.strategy ?? defaults.routing_strategy,
            routing_weights:  routing[pn.id]?.weights,
            fan_out: pn.fan_out ?? false,
          },
        }
      })

      const newEdges: SimEdge[] = preset.edges.map(([src, tgt], i) => ({
        id: `e-${src}-${tgt}-${i}`,
        source: src,
        target: tgt,
      }))

      setNodes(newNodes)
      setEdges(newEdges)
      setSimResult(null)
      setSimError(null)
      // Re-fit the viewport after React renders the new nodes
      setTimeout(() => fitView({ padding: 0.2 }), 50)
    },
    [setNodes, setEdges, fitView],
  )

  const onClear = useCallback(() => {
    setNodes([])
    setEdges([])
    setSimResult(null)
    setSimError(null)
  }, [setNodes, setEdges])

  return (
    <div className="flex flex-col w-screen h-screen bg-slate-950">
      {/* ── Top bar: brand + preset loader + clear ── */}
      <Toolbar onLoadPreset={loadPreset} onClear={onClear} />

      {/* ── Main area: palette | canvas | config ── */}
      <div className="flex flex-1 min-h-0">
        <NodePalette />

        <div className="flex-1 relative" onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={displayNodes}
            edges={displayEdges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            deleteKeyCode="Delete"
          >
            <Background variant={BackgroundVariant.Dots} color="#1e293b" gap={20} />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                const colors: Record<string, string> = {
                  load_balancer:   '#d97706',
                  app_server:      '#2563eb',
                  database:        '#16a34a',
                  cache:           '#7c3aed',
                  cdn:             '#0d9488',
                  payment_gateway: '#db2777',
                  message_queue:   '#4f46e5',
                }
                return colors[n.type ?? ''] ?? '#64748b'
              }}
              maskColor="rgba(2,6,23,0.75)"
            />
          </ReactFlow>
        </div>

        {selectedEdge && !selectedNode ? (
          <EdgeConfigPanel edge={selectedEdge} onUpdate={onUpdateEdge} />
        ) : (
          <NodeConfigPanel
            node={selectedNode}
            onUpdate={onUpdateNode}
            edges={edges}
            allNodes={nodes}
          />
        )}
      </div>

      {/* ── Results panel ── */}
      {simResult && (
        <ResultsPanel
          summary={simResult.summary}
          nodeNames={Object.fromEntries(nodes.map((n) => [n.id, n.data.name]))}
          nodeOutages={Object.fromEntries(
            nodes
              .filter((n) => Array.isArray(n.data.outages) && (n.data.outages as OutageEntry[]).length > 0)
              .map((n) => [n.id, n.data.outages as OutageEntry[]])
          )}
          onClose={() => setSimResult(null)}
        />
      )}

      {/* ── Bottom bar: simulation controls ── */}
      <SimControls onRun={onRun} running={running} error={simError} />
    </div>
  )
}
