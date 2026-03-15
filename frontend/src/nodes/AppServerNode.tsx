import type { NodeProps } from '@xyflow/react'
import { BaseNode, type NodeConfig } from './BaseNode'
import type { SimNode } from '../types'

const CONFIG: NodeConfig = {
  color: '#2563eb',
  label: 'App Server',
  abbr: 'APP',
}

export function AppServerNode({ data, selected }: NodeProps<SimNode>) {
  return <BaseNode data={data} selected={selected} config={CONFIG} />
}
