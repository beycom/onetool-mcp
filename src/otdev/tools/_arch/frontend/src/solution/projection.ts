import type {
  ArchitectureLevel,
  AbsentSelectedSystem,
  BoundaryInterface,
  CollapsedInterface,
  PreparedSolutionSnapshots,
  ProjectionDiagnostic,
  SystemSetSelector,
  ViewGraph,
  ViewGraphEdge,
  ViewGraphNode,
} from '../data/types'
import {
  BoundedCache,
  LAYOUT_SCHEMA_VERSION,
  PROJECTION_SCHEMA_VERSION,
  RENDERER_ADAPTER_VERSION,
} from './runtime'

export interface LocalSolutionProjection {
  cacheKey: string
  graph: ViewGraph
  selectedSystems: string[]
  includedSystems: string[]
  systemDistances: Record<string, number>
  absentSystems: AbsentSelectedSystem[]
  internalInterfaces: ViewGraphEdge[]
  boundaryInterfaces: BoundaryInterface[]
  collapsedInterfaces: CollapsedInterface[]
  diagnostics: ProjectionDiagnostic[]
}

export function normalizedSelector(selector: SystemSetSelector): SystemSetSelector {
  return {
    systems: [...new Set(selector.systems)].sort(),
    system_groups: [...new Set(selector.system_groups)].sort(),
    changes: [...new Set(selector.changes)].sort(),
    change_groups: [...new Set(selector.change_groups)].sort(),
    tags: [...new Set(selector.tags)].sort(),
  }
}

export function stableSelector(selector: SystemSetSelector): string {
  return JSON.stringify(normalizedSelector(selector))
}

const projectionCaches = new WeakMap<
  PreparedSolutionSnapshots,
  BoundedCache<string, LocalSolutionProjection>
>()

function projectionCache(prepared: PreparedSolutionSnapshots) {
  let cache = projectionCaches.get(prepared)
  if (!cache) {
    cache = new BoundedCache<string, LocalSolutionProjection>(32)
    projectionCaches.set(prepared, cache)
  }
  return cache
}

export function projectionCacheStats(prepared: PreparedSolutionSnapshots) {
  const cache = projectionCache(prepared)
  return { size: cache.size, hits: cache.hits, misses: cache.misses }
}

export function solutionProjectionCacheKey({
  prepared,
  snapshot,
  order,
  selector,
  interfaceDepth,
  level,
  theme,
}: {
  prepared: PreparedSolutionSnapshots
  snapshot: ViewGraph
  order: number
  selector: SystemSetSelector
  interfaceDepth: number
  level: ArchitectureLevel
  theme: string
}): string {
  return [
    PROJECTION_SCHEMA_VERSION,
    RENDERER_ADAPTER_VERSION,
    LAYOUT_SCHEMA_VERSION,
    prepared.roadmap_id,
    snapshot.id,
    order,
    stableSelector(selector),
    interfaceDepth,
    level,
    theme,
  ].join('|')
}

function stableHash(value: string): string {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

function resolveSystems(
  prepared: PreparedSolutionSnapshots,
  order: number,
  selector: SystemSetSelector,
): Set<string> {
  const indexes = prepared.indexes[String(order)]
  if (!indexes) return new Set()
  const lookups: [string, string[], Set<string>][] = [
    ['systems', selector.systems, new Set(indexes.systems)],
    ['system groups', selector.system_groups, new Set(Object.keys(indexes.system_groups))],
    ['changes', selector.changes, new Set(Object.keys(indexes.changes))],
    ['change groups', selector.change_groups, new Set(Object.keys(indexes.change_groups))],
    ['tags', selector.tags, new Set(Object.keys(indexes.tags))],
  ]
  for (const [label, values, known] of lookups) {
    const unknown = values.filter((value) => !known.has(value)).sort()
    if (unknown.length > 0) throw new Error(`Unknown ${label}: ${unknown.join(', ')}`)
  }
  const requested = Object.values(selector).some((values) => values.length > 0)
  const selected = new Set(selector.systems)
  for (const group of selector.system_groups)
    indexes.system_groups[group]?.forEach((id) => selected.add(id))
  for (const change of selector.changes)
    indexes.changes[change]?.forEach((id) => selected.add(id))
  for (const group of selector.change_groups)
    indexes.change_groups[group]?.forEach((id) => selected.add(id))
  for (const tag of selector.tags) indexes.tags[tag]?.forEach((id) => selected.add(id))
  return requested ? selected : new Set(indexes.systems)
}

function systemMap(nodes: ViewGraphNode[]): Map<string, string | undefined> {
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const result = new Map<string, string | undefined>()
  for (const node of nodes) {
    let current: ViewGraphNode | undefined = node
    const seen = new Set<string>()
    while (current && current.entity_kind !== 'system') {
      if (!current.parent || seen.has(current.id)) {
        current = undefined
        break
      }
      seen.add(current.id)
      current = byId.get(current.parent)
    }
    result.set(node.id, current?.id)
  }
  return result
}

function levelEndpoint(
  endpoint: string,
  level: ArchitectureLevel,
  nodes: Map<string, ViewGraphNode>,
): string | undefined {
  let current = nodes.get(endpoint)
  while (current) {
    if (level === 'component' || current.entity_kind === 'system') return current.id
    if (level === 'application' && current.entity_kind === 'application') return current.id
    current = current.parent ? nodes.get(current.parent) : undefined
  }
  return undefined
}

export function projectSolution(
  prepared: PreparedSolutionSnapshots,
  order: number,
  selector: SystemSetSelector,
  interfaceDepth: number,
  level: ArchitectureLevel,
  theme = 'clean',
): LocalSolutionProjection | undefined {
  if (!Number.isInteger(interfaceDepth) || interfaceDepth < 0)
    throw new Error('interfaceDepth must be a non-negative integer')
  const snapshot = prepared.snapshots[String(order)]
  if (!snapshot) return undefined
  const resolvedSelector = normalizedSelector(selector)
  const cacheKey = solutionProjectionCacheKey({
    prepared,
    snapshot,
    order,
    selector: resolvedSelector,
    interfaceDepth,
    level,
    theme,
  })
  const cached = projectionCache(prepared).get(cacheKey)
  if (cached) return cached
  const selected = resolveSystems(prepared, order, resolvedSelector)
  const systems = systemMap(snapshot.nodes)
  const presentSystems = new Set(
    snapshot.nodes
      .filter(
        (node) =>
          node.entity_kind === 'system' && !node.tombstone && !node.future,
      )
      .map((node) => node.id),
  )
  const absentSystems = [...selected]
    .filter((systemId) => !presentSystems.has(systemId))
    .sort()
    .map((systemId): AbsentSelectedSystem => {
      const presence = prepared.system_presence[systemId] ?? []
      const state =
        presence.length > 0 && order < Math.min(...presence)
          ? 'not_yet_present'
          : presence.length > 0 && order > Math.max(...presence)
            ? 'no_longer_present'
            : 'not_present'
      return { system_id: systemId, state, message: 'not present at this snapshot' }
    })
  const adjacency = new Map<string, Set<string>>()
  for (const edge of snapshot.edges) {
    if (edge.entity_kind !== 'interface') continue
    const source = systems.get(edge.source_id)
    const target = systems.get(edge.target_id)
    if (!source || !target || source === target) continue
    if (!adjacency.has(source)) adjacency.set(source, new Set())
    if (!adjacency.has(target)) adjacency.set(target, new Set())
    adjacency.get(source)!.add(target)
    adjacency.get(target)!.add(source)
  }
  const distances = new Map([...selected].map((id): [string, number] => [id, 0]))
  const included = new Set(distances.keys())
  let frontier = new Set(selected)
  for (let hop = 0; hop < interfaceDepth; hop += 1) {
    const next = new Set<string>()
    for (const system of frontier) {
      for (const neighbor of adjacency.get(system) ?? []) {
        if (!included.has(neighbor)) next.add(neighbor)
      }
    }
    next.forEach((id) => included.add(id))
    next.forEach((id) => distances.set(id, hop + 1))
    frontier = next
  }

  const internal: ViewGraphEdge[] = []
  const boundaryInterfaces: BoundaryInterface[] = []
  const diagnostics: ProjectionDiagnostic[] = []
  const snapshotNodeById = new Map(snapshot.nodes.map((node) => [node.id, node]))
  for (const edge of snapshot.edges) {
    const sourceSystem = systems.get(edge.source_id)
    const targetSystem = systems.get(edge.target_id)
    for (const [endpointId, endpointSystem] of [
      [edge.source_id, sourceSystem],
      [edge.target_id, targetSystem],
    ] as const) {
      const endpoint = snapshotNodeById.get(endpointId)
      if (!endpointSystem && endpoint?.entity_kind !== 'user') {
        diagnostics.push({
          code:
            edge.entity_kind === 'interface'
              ? 'unresolved_interface_endpoint'
              : 'unresolved_relationship_endpoint',
          message: `${edge.entity_kind} '${edge.id}' endpoint '${endpointId}' has no owning system`,
          entity_id: edge.id,
          endpoint_id: endpointId,
        })
      }
    }
    const sourceInside = included.has(sourceSystem ?? '')
    const targetInside = included.has(targetSystem ?? '')
    if (sourceInside && targetInside) internal.push(edge)
    else if (edge.entity_kind === 'interface' && sourceInside !== targetInside)
      boundaryInterfaces.push({
        interface: edge,
        inside_system: (sourceInside ? sourceSystem : targetSystem)!,
        inside_endpoint: sourceInside ? edge.source_id : edge.target_id,
        outside_system: sourceInside ? targetSystem : sourceSystem,
        outside_endpoint: sourceInside ? edge.target_id : edge.source_id,
      })
  }

  const allowed = {
    system: new Set(['system']),
    application: new Set(['system', 'application']),
    component: new Set(['system', 'application', 'component']),
  }[level]
  const nodes = snapshot.nodes.filter(
    (node) => allowed.has(node.entity_kind) && included.has(systems.get(node.id) ?? ''),
  )
  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const allNodes = new Map(snapshot.nodes.map((node) => [node.id, node]))
  const children = new Map<string, string[]>()
  for (const node of nodes) {
    if (!node.parent || !nodeById.has(node.parent)) continue
    children.set(node.parent, [...(children.get(node.parent) ?? []), node.id])
  }
  const projectedNodes = nodes.map((node) => ({
    ...node,
    children: [...(children.get(node.id) ?? [])].sort(),
  }))
  const collapsedInterfaces: CollapsedInterface[] = []
  const relationships: ViewGraphEdge[] = []
  const interfaceGroups = new Map<string, ViewGraphEdge[]>()
  for (const edge of internal) {
    const source = levelEndpoint(edge.source_id, level, allNodes)
    const target = levelEndpoint(edge.target_id, level, allNodes)
    if (!source || !target || !nodeById.has(source) || !nodeById.has(target)) continue
    const projected = { ...edge, source_id: source, target_id: target }
    if (edge.entity_kind === 'interface' && source === target) {
      collapsedInterfaces.push({
        interface: edge,
        visible_node: source,
        reason: 'collapsed_within_visible_node',
      })
      continue
    }
    if (edge.entity_kind === 'relationship') {
      relationships.push(projected)
      continue
    }
    const key = [
      source,
      target,
      edge.direction,
      edge.integration_type ?? '',
      edge.status,
      edge.context_status,
    ].join('|')
    interfaceGroups.set(key, [...(interfaceGroups.get(key) ?? []), projected])
  }
  const edges = [...relationships]
  for (const [key, values] of [...interfaceGroups].sort(([left], [right]) => left.localeCompare(right))) {
    const members = [...values].sort((left, right) => left.id.localeCompare(right.id))
    if (members.length === 1) {
      edges.push(members[0]!)
      continue
    }
    const first = members[0]!
    const memberIds = members.map((item) => item.id)
    edges.push({
      ...first,
      id: `aggregate-${stableHash([key, ...memberIds].join('|'))}`,
      name: `${members.length} interfaces`,
      description: undefined,
      interface_ids: memberIds,
      tags: [...new Set(members.flatMap((item) => item.tags))].sort(),
      related_changes: [...new Set(members.flatMap((item) => item.related_changes))].sort(),
      properties: { aggregate_members: memberIds },
    })
  }
  edges.sort((left, right) => left.id.localeCompare(right.id))
  const result: LocalSolutionProjection = {
    cacheKey,
    selectedSystems: [...selected].sort(),
    includedSystems: [...included].sort(),
    systemDistances: Object.fromEntries([...distances].sort(([left], [right]) => left.localeCompare(right))),
    absentSystems,
    internalInterfaces: internal
      .filter((edge) => edge.entity_kind === 'interface')
      .sort((left, right) => left.id.localeCompare(right.id)),
    boundaryInterfaces,
    collapsedInterfaces: collapsedInterfaces.sort((left, right) => left.interface.id.localeCompare(right.interface.id)),
    diagnostics: diagnostics.sort((left, right) =>
      `${left.entity_id}|${left.endpoint_id}|${left.code}`.localeCompare(
        `${right.entity_id}|${right.endpoint_id}|${right.code}`,
      ),
    ),
    graph: {
      ...snapshot,
      id: `solution-${stableHash(cacheKey)}`,
      selection: {
        ...snapshot.selection,
        selection: {
          ...snapshot.selection.selection,
          system_set: resolvedSelector,
          interface_depth: interfaceDepth,
          level,
          theme,
        },
      },
      nodes: projectedNodes,
      containers: [...children.keys()].sort(),
      edges,
    },
  }
  projectionCache(prepared).set(cacheKey, result)
  return result
}
