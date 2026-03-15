import type { Node, Edge } from '@xyflow/react'

// ─── Node data stored inside each React Flow node ───────────────────────────

export interface NodeData extends Record<string, unknown> {
  node_type: string
  name: string
  capacity: number
  mean_processing_time: number
  std_processing_time: number
  failure_rate: number
  hit_rate: number
  timeout: number | null
  processing_profiles: Record<string, [number, number]>
  routing_strategy?: string               // any multi-output node; maps to SimulateRequest.routing
  routing_weights?: Record<string, number> // node id → relative weight (weighted strategy only)
  fan_out?: boolean                       // if true, dispatches to ALL outgoing edges simultaneously
  outages?: OutageEntry[]                 // sustained downtime windows to schedule before running
  avg_utilization?: number                // populated after a simulation run
  is_entry?: boolean                      // true for the node with in-degree 0 (auto-detected)
}

export type SimNode = Node<NodeData>
export type SimEdge = Edge<{ latency_ms?: number | null }>

// ─── Outage schedule ─────────────────────────────────────────────────────────

export interface OutageEntry {
  start: number     // seconds into the simulation
  duration: number  // seconds
}

// ─── API request / response ──────────────────────────────────────────────────

export interface BurstConfig {
  start: number
  end: number
  multiplier: number
}

export interface SimulateRequest {
  nodes: Array<{
    id: string
    name: string
    node_type: string
    capacity: number
    mean_processing_time: number
    std_processing_time: number
    failure_rate: number
    hit_rate: number
    timeout: number | null
    processing_profiles: Record<string, [number, number]>
    fan_out: boolean
    outages: OutageEntry[]
  }>
  edges: [string, string][]
  entry_node_id: string
  routing: Record<string, { strategy: string; weights?: Record<string, number> }>
  link_latency: [string, string, number][]   // [from_id, to_id, latency_seconds]
  rate: number
  duration: number
  seed: number
  burst: BurstConfig | null
}

export interface NodeMetrics {
  arrivals: number
  completions: number
  failures: number
  avg_utilization: number
  avg_queue_size: number
  max_queue_size: number
}

export interface SimulationSummary {
  total_requests: number
  completed: number
  failed: number
  timed_out: number
  failure_rate: number
  avg_latency_ms: number
  p50_latency_ms: number
  p95_latency_ms: number
  p99_latency_ms: number
  by_type: Record<string, unknown>
  node_metrics: Record<string, NodeMetrics>
}

export interface SimulateResponse {
  summary: SimulationSummary
  sla: unknown | null
}

// ─── Preset architectures (from /api/presets) ────────────────────────────────

export interface PresetNode {
  id: string
  name: string
  capacity: number
  mean_processing_time: number
  std_processing_time: number
  failure_rate: number
  hit_rate?: number
  timeout?: number
  processing_profiles?: Record<string, [number, number]>
  fan_out?: boolean
}

export interface ArchPreset {
  name: string
  description: string
  entry_node_id: string
  nodes: PresetNode[]
  edges: [string, string][]
  routing?: Record<string, { strategy: string; weights?: Record<string, number> }>
  sla?: unknown
}
