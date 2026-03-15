import { LoadBalancerNode } from './LoadBalancerNode'
import { AppServerNode } from './AppServerNode'
import { DatabaseNode } from './DatabaseNode'
import { CacheNode } from './CacheNode'
import { CdnNode } from './CdnNode'
import { PaymentGatewayNode } from './PaymentGatewayNode'
import { MessageQueueNode } from './MessageQueueNode'

export const nodeTypes = {
  load_balancer:    LoadBalancerNode,
  app_server:       AppServerNode,
  database:         DatabaseNode,
  cache:            CacheNode,
  cdn:              CdnNode,
  payment_gateway:  PaymentGatewayNode,
  message_queue:    MessageQueueNode,
} as const

export type NodeTypeName = keyof typeof nodeTypes
