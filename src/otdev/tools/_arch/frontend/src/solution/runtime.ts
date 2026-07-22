import type { ViewGraph } from '../data/types'

export const PROJECTION_SCHEMA_VERSION = 'solution-projection-2'
export const RENDERER_ADAPTER_VERSION = 'likec4-adapter-1'
export const LAYOUT_SCHEMA_VERSION = 'solution-layout-1'

export interface ProjectionThresholds {
  warningNodes: number
  warningEdges: number
  hardNodes: number
  hardEdges: number
}

export const DEFAULT_PROJECTION_THRESHOLDS: ProjectionThresholds = {
  warningNodes: 160,
  warningEdges: 320,
  hardNodes: 500,
  hardEdges: 1_000,
}

export class BoundedCache<K, V> {
  readonly #values = new Map<K, V>()
  readonly #limit: number
  hits = 0
  misses = 0

  constructor(limit: number) {
    if (!Number.isInteger(limit) || limit < 1) throw new Error('Cache limit must be a positive integer')
    this.#limit = limit
  }

  get size(): number {
    return this.#values.size
  }

  get(key: K): V | undefined {
    const value = this.#values.get(key)
    if (value === undefined) {
      this.misses += 1
      return undefined
    }
    this.#values.delete(key)
    this.#values.set(key, value)
    this.hits += 1
    return value
  }

  set(key: K, value: V): void {
    this.#values.delete(key)
    this.#values.set(key, value)
    const oldest = this.#values.keys().next().value as K | undefined
    if (this.#values.size > this.#limit && oldest !== undefined) this.#values.delete(oldest)
  }

  has(key: K): boolean {
    return this.#values.has(key)
  }
}

export class LatestRequestGate {
  #sequence = 0
  #active = 0

  start(): number {
    this.#sequence += 1
    this.#active = this.#sequence
    return this.#active
  }

  isCurrent(requestId: number): boolean {
    return requestId === this.#active
  }

  cancel(requestId: number): void {
    if (this.isCurrent(requestId)) this.#active = 0
  }
}

export function afterInteraction(): Promise<void> {
  return new Promise((resolve) => {
    if ('requestIdleCallback' in globalThis) {
      globalThis.requestIdleCallback(() => resolve(), { timeout: 50 })
    } else {
      setTimeout(resolve, 0)
    }
  })
}

export function projectionSizeState(
  graph: ViewGraph,
  thresholds: ProjectionThresholds = DEFAULT_PROJECTION_THRESHOLDS,
): 'ok' | 'warning' | 'hard' {
  if (graph.nodes.length > thresholds.hardNodes || graph.edges.length > thresholds.hardEdges)
    return 'hard'
  if (graph.nodes.length > thresholds.warningNodes || graph.edges.length > thresholds.warningEdges)
    return 'warning'
  return 'ok'
}
