import { MarkerType, type Edge, type Node } from '@xyflow/react'

export type DiagramMode = 'path' | 'map' | 'lens'
export type DiagramTab = 'architecture' | 'sequence'

export interface PassportRelationship {
  id: string
  direction: 'IN' | 'OUT' | 'STEP'
  name: string
  detail: string
}

export interface PassportRecord {
  id: string
  name: string
  subtitle: string
  kind: 'actor' | 'service' | 'database' | 'external' | 'event' | 'relationship' | 'message'
  technology: string
  context: string
  tags: string[]
  incoming: number
  outgoing: number
  upstream: number
  downstream: number
  note?: string
  relationships: PassportRelationship[]
}

export interface ArchitectureNodeData extends Record<string, unknown> {
  label: string
  subtitle: string
  kind: PassportRecord['kind']
  icon: string
  tone: 'teal' | 'amber' | 'violet' | 'slate'
  status?: string
}

export interface BoundaryNodeData extends Record<string, unknown> {
  label: string
  tone: 'amber' | 'rose'
}

export interface SemanticEdgeData extends Record<string, unknown> {
  label: string
  kind: string
  route: boolean
  dimmed?: boolean
}

export type ArchitectureNode = Node<ArchitectureNodeData, 'architecture'>
export type BoundaryNode = Node<BoundaryNodeData, 'boundary'>
export type DiagramNode = ArchitectureNode | BoundaryNode
export type SemanticEdge = Edge<SemanticEdgeData, 'semantic'>

export const routeNodeIds = new Set([
  'buyers',
  'edge-gateway',
  'checkout-api',
  'orders',
  'payment-rail',
])

export const lensNodeIds = new Set([
  'checkout-api',
  'orders',
  'session-cache',
  'event-bus',
])

export const architectureNodes: DiagramNode[] = [
  {
    id: 'production-region',
    type: 'boundary',
    position: { x: 315, y: 35 },
    data: { label: 'Production region', tone: 'amber' },
    style: { width: 1125, height: 720 },
    width: 1125,
    height: 720,
    selectable: false,
    draggable: false,
    connectable: false,
    focusable: false,
    zIndex: -2,
  },
  {
    id: 'checkout-zone',
    type: 'boundary',
    position: { x: 675, y: 300 },
    data: { label: 'Checkout trust zone', tone: 'rose' },
    style: { width: 625, height: 335 },
    width: 625,
    height: 335,
    selectable: false,
    draggable: false,
    connectable: false,
    focusable: false,
    zIndex: -1,
  },
  {
    id: 'buyers',
    type: 'architecture',
    position: { x: 45, y: 385 },
    width: 250,
    height: 130,
    data: { label: 'Buyers', subtitle: 'Web + mobile', kind: 'actor', icon: '↗', tone: 'slate' },
  },
  {
    id: 'edge-gateway',
    type: 'architecture',
    position: { x: 355, y: 385 },
    width: 250,
    height: 130,
    data: { label: 'Edge Gateway', subtitle: 'TLS + routing', kind: 'service', icon: '☁', tone: 'amber' },
  },
  {
    id: 'checkout-api',
    type: 'architecture',
    position: { x: 710, y: 385 },
    width: 250,
    height: 130,
    data: { label: 'Checkout API', subtitle: 'v1 service', kind: 'service', icon: '〈〉', tone: 'teal', status: 'selected' },
  },
  {
    id: 'orders',
    type: 'architecture',
    position: { x: 1025, y: 385 },
    width: 250,
    height: 130,
    data: { label: 'Orders', subtitle: 'PostgreSQL', kind: 'database', icon: '▤', tone: 'violet' },
  },
  {
    id: 'session-cache',
    type: 'architecture',
    position: { x: 865, y: 105 },
    width: 250,
    height: 130,
    data: { label: 'Session Cache', subtitle: 'Redis', kind: 'database', icon: '▤', tone: 'violet' },
  },
  {
    id: 'payment-rail',
    type: 'architecture',
    position: { x: 1345, y: 385 },
    width: 250,
    height: 130,
    data: { label: 'Payment Rail', subtitle: 'external', kind: 'external', icon: '↗', tone: 'slate' },
  },
  {
    id: 'event-bus',
    type: 'architecture',
    position: { x: 825, y: 655 },
    width: 250,
    height: 130,
    data: { label: 'Order Events', subtitle: 'Kafka topic', kind: 'event', icon: '≋', tone: 'teal' },
  },
  {
    id: 'fulfilment',
    type: 'architecture',
    position: { x: 1170, y: 655 },
    width: 250,
    height: 130,
    data: { label: 'Fulfilment', subtitle: 'async worker', kind: 'service', icon: '〈〉', tone: 'teal' },
  },
]

const markerEnd = { type: MarkerType.ArrowClosed, width: 18, height: 18 }

export const architectureEdges: SemanticEdge[] = [
  {
    id: 'buyers-gateway', type: 'semantic', source: 'buyers', target: 'edge-gateway',
    sourceHandle: 'right-source', targetHandle: 'left-target', markerEnd,
    data: { label: 'HTTPS', kind: 'web', route: true },
  },
  {
    id: 'gateway-checkout', type: 'semantic', source: 'edge-gateway', target: 'checkout-api',
    sourceHandle: 'right-source', targetHandle: 'left-target', markerEnd,
    data: { label: 'checkout', kind: 'API', route: true },
  },
  {
    id: 'checkout-orders', type: 'semantic', source: 'checkout-api', target: 'orders',
    sourceHandle: 'right-source', targetHandle: 'left-target', markerEnd,
    data: { label: 'SQL', kind: 'database', route: true },
  },
  {
    id: 'orders-payment', type: 'semantic', source: 'orders', target: 'payment-rail',
    sourceHandle: 'right-source', targetHandle: 'left-target', markerEnd,
    data: { label: 'authorize', kind: 'API', route: true },
  },
  {
    id: 'checkout-session', type: 'semantic', source: 'checkout-api', target: 'session-cache',
    sourceHandle: 'top-source', targetHandle: 'bottom-target', markerEnd,
    data: { label: 'session', kind: 'cache', route: false },
  },
  {
    id: 'checkout-events', type: 'semantic', source: 'checkout-api', target: 'event-bus',
    sourceHandle: 'bottom-source', targetHandle: 'top-target', markerEnd,
    data: { label: 'accepted', kind: 'event', route: false },
  },
  {
    id: 'events-fulfilment', type: 'semantic', source: 'event-bus', target: 'fulfilment',
    sourceHandle: 'right-source', targetHandle: 'left-target', markerEnd,
    data: { label: 'order.accepted', kind: 'event', route: false },
  },
]

export const passports: Record<string, PassportRecord> = {
  buyers: {
    id: 'buyers', name: 'Buyers', subtitle: 'Web + mobile', kind: 'actor', technology: 'External actor',
    context: 'Outside Production region', tags: ['ACTOR', 'customer'], incoming: 1, outgoing: 1,
    upstream: 0, downstream: 7, note: 'Customers using web and mobile checkout.',
    relationships: [{ id: 'buyers-gateway', direction: 'OUT', name: 'Edge Gateway', detail: 'HTTPS' }],
  },
  'edge-gateway': {
    id: 'edge-gateway', name: 'Edge Gateway', subtitle: 'TLS + routing', kind: 'service', technology: 'Cloud edge',
    context: 'Production region', tags: ['EDGE', 'public'], incoming: 1, outgoing: 1, upstream: 1, downstream: 6,
    note: 'Terminates TLS and routes checkout requests.',
    relationships: [
      { id: 'buyers-gateway', direction: 'IN', name: 'Buyers', detail: 'HTTPS' },
      { id: 'gateway-checkout', direction: 'OUT', name: 'Checkout API', detail: 'checkout' },
    ],
  },
  'checkout-api': {
    id: 'checkout-api', name: 'Checkout API', subtitle: 'v1 service', kind: 'service', technology: 'TypeScript service',
    context: 'Production region › Checkout trust zone', tags: ['BACKEND', 'checkout'], incoming: 1, outgoing: 3,
    upstream: 2, downstream: 5, note: 'Selected container · coordinates the authored checkout flow.',
    relationships: [
      { id: 'gateway-checkout', direction: 'IN', name: 'Edge Gateway', detail: 'checkout' },
      { id: 'checkout-orders', direction: 'OUT', name: 'Orders', detail: 'SQL' },
      { id: 'checkout-session', direction: 'OUT', name: 'Session Cache', detail: 'session' },
      { id: 'checkout-events', direction: 'OUT', name: 'Order Events', detail: 'accepted' },
    ],
  },
  orders: {
    id: 'orders', name: 'Orders', subtitle: 'PostgreSQL', kind: 'database', technology: 'PostgreSQL 16',
    context: 'Production region › Checkout trust zone', tags: ['DATABASE', 'orders'], incoming: 1, outgoing: 1,
    upstream: 3, downstream: 2, relationships: [
      { id: 'checkout-orders', direction: 'IN', name: 'Checkout API', detail: 'SQL' },
      { id: 'orders-payment', direction: 'OUT', name: 'Payment Rail', detail: 'authorize' },
    ],
  },
  'session-cache': {
    id: 'session-cache', name: 'Session Cache', subtitle: 'Redis', kind: 'database', technology: 'Redis',
    context: 'Production region', tags: ['DATABASE', 'cache'], incoming: 1, outgoing: 0,
    upstream: 3, downstream: 0, relationships: [
      { id: 'checkout-session', direction: 'IN', name: 'Checkout API', detail: 'session' },
    ],
  },
  'payment-rail': {
    id: 'payment-rail', name: 'Payment Rail', subtitle: 'external', kind: 'external', technology: 'External provider',
    context: 'Outside Production region', tags: ['EXTERNAL', 'payments'], incoming: 1, outgoing: 0,
    upstream: 4, downstream: 0, relationships: [
      { id: 'orders-payment', direction: 'IN', name: 'Orders', detail: 'authorize' },
    ],
  },
  'event-bus': {
    id: 'event-bus', name: 'Order Events', subtitle: 'Kafka topic', kind: 'event', technology: 'Apache Kafka',
    context: 'Production region › Checkout trust zone', tags: ['EVENT', 'checkout'], incoming: 1, outgoing: 1,
    upstream: 3, downstream: 1, relationships: [
      { id: 'checkout-events', direction: 'IN', name: 'Checkout API', detail: 'accepted' },
      { id: 'events-fulfilment', direction: 'OUT', name: 'Fulfilment', detail: 'order.accepted' },
    ],
  },
  fulfilment: {
    id: 'fulfilment', name: 'Fulfilment', subtitle: 'async worker', kind: 'service', technology: 'Kubernetes worker',
    context: 'Production region', tags: ['BACKEND', 'async'], incoming: 1, outgoing: 0,
    upstream: 4, downstream: 0, relationships: [
      { id: 'events-fulfilment', direction: 'IN', name: 'Order Events', detail: 'order.accepted' },
    ],
  },
}

for (const edge of architectureEdges) {
  const source = passports[edge.source]
  const target = passports[edge.target]
  passports[edge.id] = {
    id: edge.id,
    name: edge.data?.label ?? edge.id,
    subtitle: `${source.name} → ${target.name}`,
    kind: 'relationship',
    technology: edge.data?.kind ?? 'relationship',
    context: `${source.context} → ${target.context}`,
    tags: ['RELATIONSHIP', edge.data?.kind ?? 'authored'],
    incoming: 1,
    outgoing: 1,
    upstream: source.upstream,
    downstream: target.downstream,
    note: `Pinned relationship · ${source.name} → ${target.name}`,
    relationships: [
      { id: source.id, direction: 'IN', name: source.name, detail: source.subtitle },
      { id: target.id, direction: 'OUT', name: target.name, detail: target.subtitle },
    ],
  }
}

export interface SequenceMessage {
  id: string
  from: string
  to: string
  label: string
  kind: 'sync' | 'async' | 'return'
  y: number
  route: boolean
}

export const sequenceParticipants = [
  { id: 'buyers', label: 'Buyers', subtitle: 'Web + mobile', x: 110, tone: 'slate' },
  { id: 'edge-gateway', label: 'Edge Gateway', subtitle: 'TLS + routing', x: 325, tone: 'amber' },
  { id: 'checkout-api', label: 'Checkout API', subtitle: 'v1 service', x: 550, tone: 'teal' },
  { id: 'session-cache', label: 'Session Cache', subtitle: 'Redis', x: 775, tone: 'violet' },
  { id: 'orders', label: 'Orders', subtitle: 'PostgreSQL', x: 1000, tone: 'violet' },
  { id: 'payment-rail', label: 'Payment Rail', subtitle: 'external', x: 1225, tone: 'slate' },
] as const

export const sequenceMessages: SequenceMessage[] = [
  { id: 'm1', from: 'buyers', to: 'edge-gateway', label: 'POST /checkout', kind: 'sync', y: 180, route: true },
  { id: 'm2', from: 'edge-gateway', to: 'checkout-api', label: 'checkout(command)', kind: 'sync', y: 250, route: true },
  { id: 'm3', from: 'checkout-api', to: 'session-cache', label: 'GET session', kind: 'sync', y: 320, route: true },
  { id: 'm4', from: 'session-cache', to: 'checkout-api', label: 'session', kind: 'return', y: 385, route: true },
  { id: 'm5', from: 'checkout-api', to: 'orders', label: 'create accepted order', kind: 'sync', y: 485, route: true },
  { id: 'm6', from: 'checkout-api', to: 'payment-rail', label: 'authorize(amount)', kind: 'sync', y: 555, route: true },
  { id: 'm7', from: 'payment-rail', to: 'checkout-api', label: 'approved', kind: 'return', y: 625, route: true },
  { id: 'm8', from: 'checkout-api', to: 'edge-gateway', label: '202 Accepted', kind: 'return', y: 720, route: false },
  { id: 'm9', from: 'edge-gateway', to: 'buyers', label: 'confirmation', kind: 'return', y: 785, route: false },
]

for (const message of sequenceMessages) {
  const source = passports[message.from]
  const target = passports[message.to]
  passports[message.id] = {
    id: message.id,
    name: message.label,
    subtitle: `${source.name} → ${target.name}`,
    kind: 'message',
    technology: message.kind === 'return' ? 'Return message' : 'Synchronous message',
    context: `Checkout journey · step ${sequenceMessages.indexOf(message) + 1}`,
    tags: ['MESSAGE', message.kind],
    incoming: 1,
    outgoing: 1,
    upstream: sequenceMessages.indexOf(message),
    downstream: sequenceMessages.length - sequenceMessages.indexOf(message) - 1,
    note: `Authored sequence step ${sequenceMessages.indexOf(message) + 1} of ${sequenceMessages.length}.`,
    relationships: [
      { id: source.id, direction: 'IN', name: source.name, detail: source.subtitle },
      { id: target.id, direction: 'OUT', name: target.name, detail: target.subtitle },
    ],
  }
}
