import type { NodeProps } from '@xyflow/react'
import { BaseNode, type NodeConfig } from './BaseNode'
import type { SimNode } from '../types'

const CONFIG: NodeConfig = {
  color: '#d97706',
  label: 'Load Balancer',
  abbr: 'LB',
}

export function LoadBalancerNode({ data, selected }: NodeProps<SimNode>) {
  return <BaseNode data={data} selected={selected} config={CONFIG} />
}
