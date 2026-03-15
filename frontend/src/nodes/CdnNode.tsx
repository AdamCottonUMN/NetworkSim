import type { NodeProps } from '@xyflow/react'
import { BaseNode, type NodeConfig } from './BaseNode'
import type { SimNode } from '../types'

const CONFIG: NodeConfig = {
  color: '#0d9488',
  label: 'CDN',
  abbr: 'CDN',
}

export function CdnNode({ data, selected }: NodeProps<SimNode>) {
  return <BaseNode data={data} selected={selected} config={CONFIG} />
}
