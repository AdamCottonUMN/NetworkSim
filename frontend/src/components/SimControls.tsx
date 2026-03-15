import { useState } from 'react'
import type { BurstConfig } from '../types'

interface Props {
  onRun: (params: {
    rate: number
    duration: number
    seed: number
    burst: BurstConfig | null
  }) => void
  running: boolean
  error: string | null
}

const INPUT =
  'bg-slate-800 border border-slate-700 rounded px-2.5 py-1 text-slate-200 text-sm ' +
  'focus:outline-none focus:ring-1 focus:ring-slate-500 w-24'

const LABEL = 'text-slate-400 text-xs font-medium whitespace-nowrap'

export function SimControls({ onRun, running, error }: Props) {
  const [rate, setRate] = useState(50)
  const [duration, setDuration] = useState(60)
  const [seed, setSeed] = useState(42)
  const [burstEnabled, setBurstEnabled] = useState(false)
  const [burstStart, setBurstStart] = useState(10)
  const [burstEnd, setBurstEnd] = useState(20)
  const [burstMult, setBurstMult] = useState(3)

  function handleRun() {
    onRun({
      rate,
      duration,
      seed,
      burst: burstEnabled
        ? { start: burstStart, end: burstEnd, multiplier: burstMult }
        : null,
    })
  }

  return (
    <div className="flex flex-col gap-0 border-t border-slate-800 bg-slate-900 shrink-0">
      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-red-950 border-b border-red-800 text-red-300 text-xs">
          {error}
        </div>
      )}

      <div className="flex items-center gap-6 px-4 py-3 flex-wrap">
        {/* ── Traffic params ─────────────────────────────────── */}
        <div className="flex items-center gap-2">
          <label className={LABEL}>Rate (req/s)</label>
          <input
            type="number"
            className={INPUT}
            value={rate}
            min={1}
            step={10}
            onChange={(e) => setRate(Math.max(1, Number(e.target.value)))}
          />
        </div>

        <div className="flex items-center gap-2">
          <label className={LABEL}>Duration (s)</label>
          <input
            type="number"
            className={INPUT}
            value={duration}
            min={1}
            step={10}
            onChange={(e) => setDuration(Math.max(1, Number(e.target.value)))}
          />
        </div>

        <div className="flex items-center gap-2">
          <label className={LABEL}>Seed</label>
          <input
            type="number"
            className={INPUT}
            value={seed}
            min={0}
            step={1}
            onChange={(e) => setSeed(Math.max(0, Math.round(Number(e.target.value))))}
          />
        </div>

        {/* ── Burst toggle ───────────────────────────────────── */}
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              className="accent-amber-500 w-3.5 h-3.5"
              checked={burstEnabled}
              onChange={(e) => setBurstEnabled(e.target.checked)}
            />
            <span className={LABEL}>Burst</span>
          </label>
        </div>

        {/* ── Burst params (only when enabled) ──────────────── */}
        {burstEnabled && (
          <>
            <div className="flex items-center gap-2">
              <label className={LABEL}>Start (s)</label>
              <input
                type="number"
                className={INPUT}
                value={burstStart}
                min={0}
                step={1}
                onChange={(e) => setBurstStart(Math.max(0, Number(e.target.value)))}
              />
            </div>
            <div className="flex items-center gap-2">
              <label className={LABEL}>End (s)</label>
              <input
                type="number"
                className={INPUT}
                value={burstEnd}
                min={0}
                step={1}
                onChange={(e) => setBurstEnd(Math.max(0, Number(e.target.value)))}
              />
            </div>
            <div className="flex items-center gap-2">
              <label className={LABEL}>Multiplier</label>
              <input
                type="number"
                className={INPUT}
                value={burstMult}
                min={1.1}
                step={0.5}
                onChange={(e) => setBurstMult(Math.max(1.1, Number(e.target.value)))}
              />
            </div>
          </>
        )}

        {/* ── Run button ────────────────────────────────────── */}
        <button
          onClick={handleRun}
          disabled={running}
          className={
            'ml-auto px-5 py-1.5 rounded font-semibold text-sm transition-colors ' +
            (running
              ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
              : 'bg-amber-500 hover:bg-amber-400 text-slate-950 cursor-pointer')
          }
        >
          {running ? 'Running…' : 'Run Simulation'}
        </button>
      </div>
    </div>
  )
}
