import type { SimulateRequest, SimulateResponse, ArchPreset } from './types'

const BASE = 'http://localhost:8001'

export async function simulate(req: SimulateRequest): Promise<SimulateResponse> {
  const res = await fetch(`${BASE}/api/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? 'Simulation failed')
  }
  return res.json()
}

export async function getPresets(): Promise<ArchPreset[]> {
  const res = await fetch(`${BASE}/api/presets`)
  if (!res.ok) throw new Error('Failed to load presets')
  return res.json()
}
