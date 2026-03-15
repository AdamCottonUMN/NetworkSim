import type { SimNode, SimEdge, NodeData, OutageEntry } from '../types'

interface Props {
  node: SimNode | null
  onUpdate: (id: string, patch: Partial<NodeData>) => void
  edges: SimEdge[]
  allNodes: SimNode[]
}

const INPUT =
  'bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 text-sm w-full ' +
  'focus:outline-none focus:ring-1 focus:ring-slate-500 focus:border-slate-500'

const SELECT =
  'bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 text-sm w-full ' +
  'focus:outline-none focus:ring-1 focus:ring-slate-500 cursor-pointer'

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-slate-400 text-xs font-medium">{label}</label>
      {children}
    </div>
  )
}

function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 pt-1">
      <div className="h-px flex-1 bg-slate-800" />
      <span className="text-slate-600 text-xs uppercase tracking-widest shrink-0">{label}</span>
      <div className="h-px flex-1 bg-slate-800" />
    </div>
  )
}

function numBlur(
  e: React.FocusEvent<HTMLInputElement>,
  onUpdate: (val: number) => void,
  min = 0,
) {
  const val = parseFloat(e.target.value)
  if (!isNaN(val) && val >= min) onUpdate(val)
  else e.target.value = String(e.target.defaultValue)
}

export function NodeConfigPanel({ node, onUpdate, edges, allNodes }: Props) {
  if (!node) {
    return (
      <div className="w-64 shrink-0 bg-slate-900 border-l border-slate-800 flex items-center justify-center p-6">
        <p className="text-slate-600 text-sm text-center leading-relaxed">
          Click a node to edit its properties
        </p>
      </div>
    )
  }

  const d = node.data
  const set = (key: keyof NodeData, value: unknown) => onUpdate(node.id, { [key]: value })

  // Outage helpers
  const outages: OutageEntry[] = (d.outages as OutageEntry[] | undefined) ?? []
  const addOutage    = () => set('outages', [...outages, { start: 0, duration: 10 }])
  const removeOutage = (i: number) => set('outages', outages.filter((_, idx) => idx !== i))
  const updateOutage = (i: number, field: keyof OutageEntry, val: number) =>
    set('outages', outages.map((o, idx) => (idx === i ? { ...o, [field]: val } : o)))

  // Nodes this node routes traffic to
  const downstreamIds = edges.filter((e) => e.source === node.id).map((e) => e.target)
  const hasMultipleOutputs = downstreamIds.length >= 2

  // Type-specific flags
  const showHitRate = d.node_type === 'cache' || d.node_type === 'cdn'

  // Routing state
  const currentStrategy = (d.routing_strategy as string) ?? 'first'
  const currentWeights  = (d.routing_weights  as Record<string, number>) ?? {}

  return (
    <div className="w-64 shrink-0 bg-slate-900 border-l border-slate-800 flex flex-col">
      <div className="px-4 py-3 border-b border-slate-800">
        <p className="text-slate-400 text-xs font-semibold uppercase tracking-widest">
          Node Properties
        </p>
      </div>

      {/* key resets uncontrolled number inputs when a different node is selected */}
      <div key={node.id} className="p-4 flex flex-col gap-4 overflow-y-auto flex-1">

        {/* ── Name ─────────────────────────────────────────── */}
        <Field label="Name">
          <input
            type="text"
            className={INPUT}
            value={d.name}
            onChange={(e) => set('name', e.target.value)}
          />
        </Field>

        <SectionDivider label="Performance" />

        {/* ── Capacity ─────────────────────────────────────── */}
        <Field label="Capacity (concurrent slots)">
          <input
            type="number"
            className={INPUT}
            defaultValue={d.capacity}
            min={1}
            step={1}
            onBlur={(e) => numBlur(e, (v) => set('capacity', Math.round(v)), 1)}
          />
        </Field>

        {/* ── Avg latency ──────────────────────────────────── */}
        <Field label="Avg Latency (ms)">
          <input
            type="number"
            className={INPUT}
            defaultValue={+(d.mean_processing_time * 1000).toFixed(1)}
            min={0.1}
            step={1}
            onBlur={(e) =>
              numBlur(e, (v) => set('mean_processing_time', v / 1000), 0.1)
            }
          />
        </Field>

        {/* ── Std dev ──────────────────────────────────────── */}
        <Field label="Latency Std Dev (ms)">
          <input
            type="number"
            className={INPUT}
            defaultValue={+(d.std_processing_time * 1000).toFixed(1)}
            min={0}
            step={0.5}
            onBlur={(e) =>
              numBlur(e, (v) => set('std_processing_time', v / 1000), 0)
            }
          />
        </Field>

        <SectionDivider label="Reliability" />

        {/* ── Failure rate ─────────────────────────────────── */}
        <Field label="Failure Rate (%)">
          <input
            type="number"
            className={INPUT}
            defaultValue={+(d.failure_rate * 100).toFixed(2)}
            min={0}
            max={100}
            step={0.1}
            onBlur={(e) =>
              numBlur(e, (v) => set('failure_rate', Math.min(v / 100, 1)), 0)
            }
          />
        </Field>

        {/* ── Timeout ──────────────────────────────────────── */}
        <Field label="Queue Timeout (ms, blank = off)">
          <input
            type="number"
            className={INPUT}
            defaultValue={d.timeout != null ? d.timeout * 1000 : ''}
            min={0}
            step={10}
            placeholder="disabled"
            onBlur={(e) => {
              const raw = e.target.value.trim()
              if (raw === '') { set('timeout', null); return }
              const v = parseFloat(raw)
              if (!isNaN(v) && v >= 0) set('timeout', v / 1000)
            }}
          />
        </Field>

        {/* ── Outages ──────────────────────────────────────────── */}
        <SectionDivider label="Outages" />
        {outages.map((o, i) => (
          <div
            key={`${node.id}-${outages.length}-${i}`}
            className="flex gap-2 items-end"
          >
            <div className="flex flex-col gap-1.5 flex-1">
              <label className="text-slate-400 text-xs font-medium">Start (s)</label>
              <input
                type="number"
                className={INPUT}
                defaultValue={o.start}
                min={0}
                step={1}
                onBlur={(e) => {
                  const v = parseFloat(e.target.value)
                  if (!isNaN(v) && v >= 0) updateOutage(i, 'start', v)
                }}
              />
            </div>
            <div className="flex flex-col gap-1.5 flex-1">
              <label className="text-slate-400 text-xs font-medium">Duration (s)</label>
              <input
                type="number"
                className={INPUT}
                defaultValue={o.duration}
                min={1}
                step={1}
                onBlur={(e) => {
                  const v = parseFloat(e.target.value)
                  if (!isNaN(v) && v > 0) updateOutage(i, 'duration', v)
                }}
              />
            </div>
            <button
              onClick={() => removeOutage(i)}
              className="pb-1.5 text-slate-600 hover:text-red-400 text-base cursor-pointer"
              aria-label="Remove outage"
            >
              ×
            </button>
          </div>
        ))}
        <button
          onClick={addOutage}
          className="text-slate-500 hover:text-slate-300 text-xs cursor-pointer text-left"
        >
          + Add Outage
        </button>

        {/* ── Hit rate (cache + CDN) ────────────────────────── */}
        {showHitRate && (
          <>
            <SectionDivider label={d.node_type === 'cdn' ? 'CDN' : 'Cache'} />
            <Field label="Hit Rate (%)">
              <input
                type="number"
                className={INPUT}
                defaultValue={+(d.hit_rate * 100).toFixed(0)}
                min={0}
                max={100}
                step={1}
                onBlur={(e) =>
                  numBlur(e, (v) => set('hit_rate', Math.min(v / 100, 1)), 0)
                }
              />
            </Field>
          </>
        )}

        {/* ── Routing (any node with 2+ outgoing edges) ─────── */}
        {hasMultipleOutputs && (
          <>
            <SectionDivider label="Routing" />

            {/* Fan-out toggle */}
            <Field label="Mode">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="accent-indigo-500 w-4 h-4"
                  checked={!!(d.fan_out)}
                  onChange={(e) => set('fan_out', e.target.checked)}
                />
                <span className="text-slate-300 text-sm">
                  {d.fan_out ? 'Fan-out (scatter-gather)' : 'Route to one'}
                </span>
              </label>
              <p className="text-slate-600 text-xs leading-relaxed">
                Fan-out sends to all outputs in parallel. Parent completes only when every branch finishes.
              </p>
            </Field>

            <Field label="Routing Strategy">
              <select
                className={SELECT}
                value={currentStrategy}
                onChange={(e) => set('routing_strategy', e.target.value)}
              >
                <option value="first">First (default)</option>
                <option value="round_robin">Round Robin</option>
                <option value="random">Random</option>
                <option value="weighted">Weighted</option>
              </select>
            </Field>

            {/* Weight inputs — keyed on downstream IDs so they reset if topology changes */}
            {currentStrategy === 'weighted' && (
              <div key={downstreamIds.join('|')} className="flex flex-col gap-3">
                {downstreamIds.map((id) => {
                  const name = allNodes.find((n) => n.id === id)?.data.name ?? id
                  return (
                    <Field key={id} label={`Weight → ${name}`}>
                      <input
                        type="number"
                        className={INPUT}
                        defaultValue={currentWeights[id] ?? 1}
                        min={0.1}
                        step={0.1}
                        onBlur={(e) =>
                          numBlur(e, (v) => {
                            set('routing_weights', { ...currentWeights, [id]: v })
                          }, 0.1)
                        }
                      />
                    </Field>
                  )
                })}
                <p className="text-slate-600 text-xs leading-relaxed">
                  Relative weights — don't need to sum to 1.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
