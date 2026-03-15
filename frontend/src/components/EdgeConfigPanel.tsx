import type { SimEdge } from '../types'

interface Props {
  edge: SimEdge
  onUpdate: (id: string, patch: { latency_ms: number | null }) => void
}

const INPUT =
  'bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 text-sm w-full ' +
  'focus:outline-none focus:ring-1 focus:ring-slate-500 focus:border-slate-500'

export function EdgeConfigPanel({ edge, onUpdate }: Props) {
  const latencyMs = edge.data?.latency_ms ?? null

  return (
    <div className="w-64 shrink-0 bg-slate-900 border-l border-slate-800 flex flex-col">
      <div className="px-4 py-3 border-b border-slate-800">
        <p className="text-slate-400 text-xs font-semibold uppercase tracking-widest">
          Wire Properties
        </p>
      </div>

      <div key={edge.id} className="p-4 flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-slate-400 text-xs font-medium">
            Link Latency (ms, blank = none)
          </label>
          <input
            type="number"
            className={INPUT}
            defaultValue={latencyMs ?? ''}
            min={0}
            step={1}
            placeholder="0 (instantaneous)"
            onBlur={(e) => {
              const raw = e.target.value.trim()
              if (raw === '') { onUpdate(edge.id, { latency_ms: null }); return }
              const v = parseFloat(raw)
              if (!isNaN(v) && v >= 0) onUpdate(edge.id, { latency_ms: v })
            }}
          />
          <p className="text-slate-600 text-xs leading-relaxed">
            Fixed transit delay added to every request crossing this link.
            Useful for modelling cross-region hops or WAN latency.
          </p>
        </div>
      </div>
    </div>
  )
}
