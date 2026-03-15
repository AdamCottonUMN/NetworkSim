import type { NodeProps } from '@xyflow/react'
import { BaseNode, type NodeConfig } from './BaseNode'
import type { SimNode } from '../types'

const CONFIG: NodeConfig = {
  color: '#4f46e5',
  label: 'Message Queue',
  abbr: 'QUEUE',
}

export function MessageQueueNode({ data, selected }: NodeProps<SimNode>) {
  return <BaseNode data={data} selected={selected} config={CONFIG} />
}
