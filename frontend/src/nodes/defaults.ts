import type { NodeData } from '../types'
import type { NodeTypeName } from './index'

export const NODE_DEFAULTS: Record<NodeTypeName, NodeData> = {
  load_balancer: {
    node_type: 'load_balancer',
    name: 'Load Balancer',
    capacity: 100,
    mean_processing_time: 0.003,
    std_processing_time: 0.001,
    failure_rate: 0,
    hit_rate: 0,
    timeout: null,
    processing_profiles: {},
    routing_strategy: 'first',
  },
  app_server: {
    node_type: 'app_server',
    name: 'App Server',
    capacity: 20,
    mean_processing_time: 0.08,
    std_processing_time: 0.02,
    failure_rate: 0.01,
    hit_rate: 0,
    timeout: null,
    processing_profiles: {},
  },
  database: {
    node_type: 'database',
    name: 'Database',
    capacity: 5,
    mean_processing_time: 0.05,
    std_processing_time: 0.01,
    failure_rate: 0,
    hit_rate: 0,
    timeout: null,
    processing_profiles: {},
  },
  cache: {
    node_type: 'cache',
    name: 'Cache',
    capacity: 100,
    mean_processing_time: 0.002,
    std_processing_time: 0.0005,
    failure_rate: 0,
    hit_rate: 0.8,
    timeout: null,
    processing_profiles: {},
  },
  cdn: {
    node_type: 'cdn',
    name: 'CDN',
    capacity: 500,
    mean_processing_time: 0.0005,  // 0.5 ms — edge server
    std_processing_time: 0.0001,
    failure_rate: 0,
    hit_rate: 0.95,                // 95% of requests served from edge
    timeout: null,
    processing_profiles: {},
  },
  payment_gateway: {
    node_type: 'payment_gateway',
    name: 'Payment Gateway',
    capacity: 20,                  // external API rate limit
    mean_processing_time: 0.3,     // 300 ms — typical Stripe latency
    std_processing_time: 0.05,
    failure_rate: 0.01,            // 1% payment failures
    hit_rate: 0,
    timeout: 5,                    // 5 s hard timeout
    processing_profiles: {},
  },
  message_queue: {
    node_type: 'message_queue',
    name: 'Message Queue',
    capacity: 50,                  // concurrent workers draining the queue
    mean_processing_time: 0.2,     // 200 ms per job
    std_processing_time: 0.05,
    failure_rate: 0.002,           // 0.2% job failures
    hit_rate: 0,
    timeout: null,
    processing_profiles: {},
  },
}
