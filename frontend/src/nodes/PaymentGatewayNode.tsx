import type { NodeProps } from '@xyflow/react'
import { BaseNode, type NodeConfig } from './BaseNode'
import type { SimNode } from '../types'

const CONFIG: NodeConfig = {
  color: '#db2777',
  label: 'Payment Gateway',
  abbr: 'PAY',
}

export function PaymentGatewayNode({ data, selected }: NodeProps<SimNode>) {
  return <BaseNode data={data} selected={selected} config={CONFIG} />
}
