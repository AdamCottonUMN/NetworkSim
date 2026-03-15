import { useEffect, useState } from 'react'
import { getPresets } from '../api'
import type { ArchPreset } from '../types'

interface Props {
  onLoadPreset: (preset: ArchPreset) => void
  onClear: () => void
}

const SELECT =
  'bg-slate-800 border border-slate-700 rounded px-2.5 py-1 text-slate-200 text-sm ' +
  'focus:outline-none focus:ring-1 focus:ring-slate-500 cursor-pointer ' +
  'disabled:opacity-40 disabled:cursor-not-allowed'

export function Toolbar({ onLoadPreset, onClear }: Props) {
  const [presets, setPresets] = useState<ArchPreset[]>([])
  const [selected, setSelected] = useState('')

  useEffect(() => {
    getPresets().then(setPresets).catch(() => {})
  }, [])

  function handleSelect(e: React.ChangeEvent<HTMLSelectElement>) {
    const name = e.target.value
    setSelected(name)
    const preset = presets.find((p) => p.name === name)
    if (preset) {
      onLoadPreset(preset)
      // Reset dropdown after a tick so React finishes the state update first
      setTimeout(() => setSelected(''), 0)
    }
  }

  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-slate-900 border-b border-slate-800 shrink-0">
      {/* Brand */}
      <span className="text-slate-200 font-bold text-sm tracking-wide select-none">
        NetworkSim
      </span>

      <div className="w-px h-4 bg-slate-700" />

      {/* Preset loader */}
      <div className="flex items-center gap-2">
        <label className="text-slate-500 text-xs whitespace-nowrap">Load preset:</label>
        <select
          className={SELECT}
          value={selected}
          onChange={handleSelect}
          disabled={presets.length === 0}
        >
          <option value="" disabled>
            {presets.length === 0 ? 'backend offline' : '— choose —'}
          </option>
          {presets.map((p) => (
            <option key={p.name} value={p.name}>
              {p.description ?? p.name}
            </option>
          ))}
        </select>
      </div>

      <div className="w-px h-4 bg-slate-700" />

      {/* Clear */}
      <button
        onClick={onClear}
        className="px-3 py-1 rounded text-xs text-slate-400 border border-slate-700
                   hover:text-slate-200 hover:border-slate-500 transition-colors cursor-pointer"
      >
        Clear Canvas
      </button>
    </div>
  )
}
