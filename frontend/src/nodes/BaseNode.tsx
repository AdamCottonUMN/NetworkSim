import { Handle, Position } from '@xyflow/react'
import type { NodeData } from '../types'

export interface NodeConfig {
  color: string
  label: string
  abbr: string
}

interface BaseNodeProps {
  data: NodeData
  selected: boolean
  config: NodeConfig
}

function utilColor(u: number) {
  if (u > 0.8) return '#ef4444'
  if (u > 0.6) return '#f59e0b'
  return '#22c55e'
}

export function BaseNode({ data, selected, config }: BaseNodeProps) {
  const util = data.avg_utilization

  return (
    <div style={{ position: 'relative', fontFamily: 'system-ui, sans-serif' }}>
      {/* Entry node badge — floats above the card */}
      {data.is_entry && (
        <div style={{
          position: 'absolute',
          top: -20,
          left: '50%',
          transform: 'translateX(-50%)',
          background: '#f59e0b',
          color: '#0f172a',
          fontSize: 9,
          fontWeight: 800,
          padding: '1px 7px',
          borderRadius: 4,
          letterSpacing: '0.1em',
          whiteSpace: 'nowrap',
          pointerEvents: 'none',
        }}>
          ▶ ENTRY
        </div>
      )}
    <div style={{
      width: 210,
      borderRadius: 8,
      overflow: 'hidden',
      border: `2px solid ${selected ? '#fff' : config.color}`,
      boxShadow: selected
        ? `0 0 0 3px ${config.color}55, 0 4px 16px rgba(0,0,0,0.5)`
        : '0 4px 12px rgba(0,0,0,0.4)',
    }}>
      <Handle
        type="target"
        position={Position.Left}
        style={{ width: 10, height: 10, background: config.color, border: '2px solid #0f172a' }}
      />

      {/* Header */}
      <div style={{
        background: config.color,
        padding: '5px 10px',
        display: 'flex',
        alignItems: 'center',
        gap: 7,
      }}>
        <span style={{
          background: 'rgba(0,0,0,0.25)',
          borderRadius: 4,
          padding: '1px 6px',
          fontSize: 10,
          fontWeight: 700,
          color: '#fff',
          letterSpacing: '0.08em',
          flexShrink: 0,
        }}>
          {config.abbr}
        </span>
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.9)', fontWeight: 500 }}>
          {config.label}
        </span>
      </div>

      {/* Body */}
      <div style={{ background: '#1e293b', padding: '8px 10px' }}>
        <div style={{
          color: '#f1f5f9',
          fontWeight: 600,
          fontSize: 13,
          marginBottom: 5,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {data.name}
        </div>

        <div style={{ color: '#94a3b8', fontSize: 11, lineHeight: 1.7 }}>
          <div>Capacity: <span style={{ color: '#cbd5e1' }}>{data.capacity}</span></div>
          <div>Latency: <span style={{ color: '#cbd5e1' }}>{(data.mean_processing_time * 1000).toFixed(0)} ms avg</span></div>
          {data.failure_rate > 0 && (
            <div>Fail rate: <span style={{ color: '#fca5a5' }}>{(data.failure_rate * 100).toFixed(1)}%</span></div>
          )}
          {data.hit_rate > 0 && (
            <div>Hit rate: <span style={{ color: '#86efac' }}>{(data.hit_rate * 100).toFixed(0)}%</span></div>
          )}
          {data.fan_out && (
            <div style={{ color: '#818cf8', fontWeight: 600 }}>⊕ Fan-out</div>
          )}
        </div>

        {util !== undefined && (
          <div style={{
            marginTop: 7,
            padding: '2px 8px',
            borderRadius: 4,
            background: utilColor(util),
            color: '#fff',
            fontSize: 11,
            fontWeight: 600,
            display: 'inline-block',
          }}>
            {(util * 100).toFixed(0)}% utilization
          </div>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        style={{ width: 10, height: 10, background: config.color, border: '2px solid #0f172a' }}
      />
    </div>
    </div>
  )
}
