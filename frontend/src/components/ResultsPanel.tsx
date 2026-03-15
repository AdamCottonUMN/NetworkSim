import type { SimulationSummary, NodeMetrics, OutageEntry } from '../types'

function downloadJSON(summary: SimulationSummary) {
  const blob = new Blob([JSON.stringify(summary, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `networksim-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

interface Props {
  summary: SimulationSummary
  nodeNames: Record<string, string>        // id → display name
  nodeOutages: Record<string, OutageEntry[]>  // id → configured outage windows
  onClose: () => void
}

// ─── helpers ────────────────────────────────────────────────────────────────

function utilColor(u: number) {
  if (u > 0.8) return '#ef4444'
  if (u > 0.6) return '#f59e0b'
  return '#22c55e'
}

function StatCard({
  label,
  value,
  sub,
  warn,
}: {
  label: string
  value: string
  sub?: string
  warn?: boolean
}) {
  return (
    <div className="flex flex-col gap-0.5 bg-slate-800 rounded px-3 py-2 min-w-[90px]">
      <span className="text-slate-500 text-[10px] uppercase tracking-wider font-medium">
        {label}
      </span>
      <span className={`text-lg font-bold leading-tight ${warn ? 'text-red-400' : 'text-slate-100'}`}>
        {value}
      </span>
      {sub && <span className="text-slate-500 text-[10px]">{sub}</span>}
    </div>
  )
}

function LatencyCell({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="text-slate-500 text-[10px] uppercase tracking-wider">{label}</span>
      <span className="text-slate-200 text-sm font-semibold">{value.toFixed(1)} ms</span>
    </div>
  )
}

function UtilBar({
  name,
  metrics,
  outages,
}: {
  name: string
  metrics: NodeMetrics
  outages?: OutageEntry[]
}) {
  const pct = Math.min(metrics.avg_utilization * 100, 100)
  const color = utilColor(metrics.avg_utilization)
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-2">
        <span
          className="text-slate-400 text-xs text-right shrink-0 overflow-hidden text-ellipsis whitespace-nowrap"
          style={{ width: 110 }}
          title={name}
        >
          {name}
        </span>
        <div className="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
          <div
            className="h-2 rounded-full transition-all"
            style={{ width: `${pct}%`, background: color }}
          />
        </div>
        <span className="text-xs font-semibold shrink-0" style={{ color, width: 36 }}>
          {pct.toFixed(0)}%
        </span>
        <span className="text-slate-500 text-[10px] shrink-0" style={{ width: 60 }}>
          q̄ {metrics.avg_queue_size.toFixed(1)}
        </span>
      </div>
      {outages && outages.length > 0 && (
        <div className="flex gap-1 flex-wrap" style={{ marginLeft: 118 }}>
          {outages.map((o, i) => (
            <span
              key={i}
              className="text-[9px] text-red-400 bg-red-950 rounded px-1.5 py-0.5 leading-none"
            >
              ↓ {o.start}s–{o.start + o.duration}s
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── main component ──────────────────────────────────────────────────────────

export function ResultsPanel({ summary, nodeNames, nodeOutages, onClose }: Props) {
  const failPct = (summary.failure_rate * 100).toFixed(1)
  const completedPct =
    summary.total_requests > 0
      ? ((summary.completed / summary.total_requests) * 100).toFixed(1)
      : '0'

  const nodeEntries = Object.entries(summary.node_metrics).sort(
    ([, a], [, b]) => b.avg_utilization - a.avg_utilization,
  )

  return (
    <div className="border-t border-slate-700 bg-slate-900 shrink-0 max-h-52 overflow-y-auto">
      {/* Header row */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800 sticky top-0 bg-slate-900 z-10">
        <span className="text-slate-400 text-xs font-semibold uppercase tracking-widest">
          Simulation Results
        </span>
        <div className="flex items-center gap-3">
          <button
            onClick={() => downloadJSON(summary)}
            className="text-slate-500 hover:text-slate-200 text-xs transition-colors cursor-pointer"
          >
            Export JSON
          </button>
          <button
            onClick={onClose}
            className="text-slate-600 hover:text-slate-300 text-xs leading-none cursor-pointer"
            aria-label="Close results"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="px-4 py-3 flex gap-6 flex-wrap">
        {/* ── Summary stats ── */}
        <div className="flex gap-2 flex-wrap">
          <StatCard label="Total" value={summary.total_requests.toLocaleString()} />
          <StatCard
            label="Completed"
            value={summary.completed.toLocaleString()}
            sub={`${completedPct}%`}
          />
          <StatCard
            label="Failed"
            value={summary.failed.toLocaleString()}
            sub={`${failPct}%`}
            warn={summary.failed > 0}
          />
          {summary.timed_out > 0 && (
            <StatCard
              label="Timed Out"
              value={summary.timed_out.toLocaleString()}
              warn
            />
          )}
        </div>

        {/* ── Latency breakdown ── */}
        <div className="flex flex-col justify-center gap-1">
          <span className="text-slate-500 text-[10px] uppercase tracking-wider font-medium mb-0.5">
            Latency
          </span>
          <div className="flex gap-4 bg-slate-800 rounded px-3 py-2">
            <LatencyCell label="avg" value={summary.avg_latency_ms} />
            <div className="w-px bg-slate-700" />
            <LatencyCell label="p50" value={summary.p50_latency_ms} />
            <LatencyCell label="p95" value={summary.p95_latency_ms} />
            <LatencyCell label="p99" value={summary.p99_latency_ms} />
          </div>
        </div>

        {/* ── Node utilization bars ── */}
        {nodeEntries.length > 0 && (
          <div className="flex flex-col gap-1.5 min-w-[280px] flex-1">
            <span className="text-slate-500 text-[10px] uppercase tracking-wider font-medium">
              Node Utilization
            </span>
            {nodeEntries.map(([id, metrics]) => (
              <UtilBar
                key={id}
                name={nodeNames[id] ?? id}
                metrics={metrics}
                outages={nodeOutages[id]}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
