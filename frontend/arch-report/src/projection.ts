import {
  ENTITY_KINDS,
  KINDS,
  type EntityKind,
  type FieldChange,
  type GraphBoundary,
  type GraphEdge,
  type GraphNode,
  type Level,
  type ProjectedState,
  type ProjectedView,
  type ReportPayload,
  type ReportRow,
  type RolledGraph,
  type RowKind,
  type RowRef,
  type ScopedState,
  type ScopeSelection,
  type StateDiff,
  type View,
} from './types'

const ENTITY_KIND_SET = new Set<RowKind>(ENTITY_KINDS)
const OMITTED_DIFF_FIELDS = new Set(['id', 'start_in', 'end_in', 'intervals', 'properties'])

function within(start: number, end: number | null, position: number): boolean {
  return start <= position && (end === null || position <= end)
}

export function liveAt(row: ReportRow, timeline: number, position: number): boolean {
  return row.intervals[timeline]?.live.some(([start, end]) => within(start, end, position)) ?? false
}

export function clipAt(row: ReportRow, timeline: number, position: number): string | null {
  return row.intervals[timeline]?.clips.find(({ start, end }) => within(start, end, position))?.by ?? null
}

function emptyRows(): Record<RowKind, ReportRow[]> {
  return Object.fromEntries(KINDS.map((kind) => [kind, []])) as unknown as Record<RowKind, ReportRow[]>
}

function emptyClips(): ProjectedState['clips'] {
  return Object.fromEntries(KINDS.map((kind) => [kind, new Map()])) as unknown as ProjectedState['clips']
}

export function stateAt(payload: ReportPayload, timeline: number, position: number): ProjectedState {
  const rows = emptyRows()
  const clips = emptyClips()
  for (const kind of KINDS) {
    for (const row of payload.rows[kind]) {
      if (liveAt(row, timeline, position)) rows[kind].push(row)
      const by = clipAt(row, timeline, position)
      if (by !== null) clips[kind].set(row.id, { kind, row, by })
    }
  }
  return { rows, clips }
}

function rowName(row: ReportRow): string {
  return row.name ?? row.action ?? row.id
}

function valuesEqual(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}

function changedFields(oldRow: ReportRow, newRow: ReportRow): FieldChange[] {
  const changes: FieldChange[] = []
  const fields = [...new Set([...Object.keys(oldRow), ...Object.keys(newRow)])]
  for (const field of fields) {
    if (OMITTED_DIFF_FIELDS.has(field)) continue
    const oldValue = oldRow[field as keyof ReportRow]
    const newValue = newRow[field as keyof ReportRow]
    if (!valuesEqual(oldValue, newValue)) {
      changes.push({ field, old: oldValue ?? null, new: newValue ?? null })
    }
  }
  const oldProperties = oldRow.properties ?? {}
  const newProperties = newRow.properties ?? {}
  const propertyKeys = [...new Set([...Object.keys(oldProperties), ...Object.keys(newProperties)])]
  for (const key of propertyKeys) {
    if (!valuesEqual(oldProperties[key], newProperties[key])) {
      changes.push({
        field: `properties.${key}`,
        old: oldProperties[key] ?? null,
        new: newProperties[key] ?? null,
      })
    }
  }
  return changes
}

export function diffStates(
  payload: ReportPayload,
  timeline: number,
  fromPosition: number,
  toPosition: number,
): StateDiff {
  const before = stateAt(payload, timeline, fromPosition)
  const after = stateAt(payload, timeline, toPosition)
  const diff: StateDiff = { added: [], removed: [], changed: [] }
  for (const kind of KINDS) {
    const beforeById = new Map(before.rows[kind].map((row) => [row.id, row]))
    const afterById = new Map(after.rows[kind].map((row) => [row.id, row]))
    const authoredIds = [...new Set(payload.rows[kind].map((row) => row.id))]
    for (const id of authoredIds) {
      const oldRow = beforeById.get(id)
      const newRow = afterById.get(id)
      if (!oldRow && newRow) diff.added.push({ kind, id, name: rowName(newRow) })
      if (oldRow && !newRow) {
        diff.removed.push({
          kind,
          id,
          name: rowName(oldRow),
          clipped_by: after.clips[kind].get(id)?.by ?? null,
        })
      }
      if (oldRow && newRow && oldRow !== newRow) {
        const changes = changedFields(oldRow, newRow)
        if (changes.length) diff.changed.push({ kind, id, changes })
      }
    }
  }
  return diff
}

function entityRows(state: ProjectedState): RowRef[] {
  return ENTITY_KINDS.flatMap((kind) => state.rows[kind].map((row) => ({ kind, row })))
}

function nodeKey(kind: EntityKind, id: string): string {
  return `${kind}:${id}`
}

function idIndex(state: ProjectedState): Map<string, RowRef> {
  const index = new Map<string, RowRef>()
  for (const ref of entityRows(state)) {
    index.set(nodeKey(ref.kind as EntityKind, ref.row.id), ref)
    if (!index.has(ref.row.id)) index.set(ref.row.id, ref)
  }
  return index
}

function parentRef(ref: RowRef, byId: Map<string, RowRef>): RowRef | null {
  if (ref.kind === 'subsystems' && ref.row.parent) {
    return byId.get(`systems:${ref.row.parent}`) ?? null
  }
  if (ref.kind === 'containers' && ref.row.parent) {
    return byId.get(`systems:${ref.row.parent}`)
      ?? byId.get(`subsystems:${ref.row.parent}`)
      ?? null
  }
  if (ref.kind === 'components' && ref.row.container) {
    return byId.get(`containers:${ref.row.container}`) ?? null
  }
  if (ref.kind === 'code' && ref.row.component) {
    return byId.get(`components:${ref.row.component}`) ?? null
  }
  return null
}

function topRepresentative(ref: RowRef, byId: Map<string, RowRef>): RowRef | null {
  const seen = new Set<string>()
  let cursor: RowRef | null = ref
  while (cursor && cursor.kind !== 'systems' && cursor.kind !== 'users') {
    const key = nodeKey(cursor.kind as EntityKind, cursor.row.id)
    if (seen.has(key)) return null
    seen.add(key)
    cursor = parentRef(cursor, byId)
  }
  return cursor
}

function ancestorOfKind(
  ref: RowRef,
  kind: EntityKind,
  byId: Map<string, RowRef>,
): RowRef | null {
  const seen = new Set<string>()
  let cursor: RowRef | null = ref
  while (cursor && cursor.kind !== kind) {
    const key = nodeKey(cursor.kind as EntityKind, cursor.row.id)
    if (seen.has(key)) return null
    seen.add(key)
    cursor = parentRef(cursor, byId)
  }
  return cursor
}

function endpoints(row: ReportRow): [string, string] | null {
  const left = row.provider ?? row.source
  const right = row.consumer ?? row.target
  return left && right ? [left, right] : null
}

function connectionRepresentatives(row: ReportRow, byId: Map<string, RowRef>): [RowRef, RowRef] | null {
  const pair = endpoints(row)
  if (!pair) return null
  const left = byId.get(pair[0])
  const right = byId.get(pair[1])
  if (!left || !right) return null
  const leftTop = topRepresentative(left, byId)
  const rightTop = topRepresentative(right, byId)
  return leftTop && rightTop ? [leftTop, rightTop] : null
}

function copyClips(state: ProjectedState): ProjectedState['clips'] {
  return Object.fromEntries(KINDS.map((kind) => [kind, new Map(state.clips[kind])])) as unknown as ProjectedState['clips']
}

export function scopeAt(state: ProjectedState, scope: ScopeSelection): ScopedState {
  const allEntities = entityRows(state)
  const allById = idIndex(state)
  if (scope === null) {
    const representatives = allEntities
      .map((ref) => topRepresentative(ref, allById))
      .filter((ref): ref is RowRef => ref !== null)
    return {
      rows: Object.fromEntries(KINDS.map((kind) => [kind, [...state.rows[kind]]])) as unknown as Record<RowKind, ReportRow[]>,
      clips: copyClips(state),
      boundaryStubs: new Map(),
      entityLookup: allById,
      keptRepresentatives: new Set(representatives.map((ref) => nodeKey(ref.kind as EntityKind, ref.row.id))),
    }
  }

  const liveSystems = new Set(state.rows.systems.map((row) => row.id))
  const selected = scope.systems.filter((id) => liveSystems.has(id)).map((id) => `systems:${id}`)
  const graph = new Map<string, Set<string>>()
  for (const row of state.rows.interfaces) {
    const reps = connectionRepresentatives(row, allById)
    if (!reps) continue
    const left = nodeKey(reps[0].kind as EntityKind, reps[0].row.id)
    const right = nodeKey(reps[1].kind as EntityKind, reps[1].row.id)
    if (left === right) continue
    if (!graph.has(left)) graph.set(left, new Set())
    if (!graph.has(right)) graph.set(right, new Set())
    graph.get(left)!.add(right)
    graph.get(right)!.add(left)
  }

  const kept = new Set(selected)
  let frontier = selected
  for (let step = 0; step < scope.hops; step += 1) {
    const next: string[] = []
    for (const key of frontier) {
      for (const neighbor of graph.get(key) ?? []) {
        if (!kept.has(neighbor)) {
          kept.add(neighbor)
          next.push(neighbor)
        }
      }
    }
    frontier = next
  }

  const rows = emptyRows()
  for (const ref of allEntities) {
    const representative = topRepresentative(ref, allById)
    if (representative && kept.has(nodeKey(representative.kind as EntityKind, representative.row.id))) {
      rows[ref.kind].push(ref.row)
    }
  }
  const boundaryStubs = new Map<string, RowRef>()
  for (const kind of ['interfaces', 'relationships'] as const) {
    for (const row of state.rows[kind]) {
      const reps = connectionRepresentatives(row, allById)
      if (!reps) continue
      const keys = reps.map((ref) => nodeKey(ref.kind as EntityKind, ref.row.id))
      if (!keys.some((key) => kept.has(key))) continue
      rows[kind].push(row)
      reps.forEach((ref, index) => {
        if (!kept.has(keys[index])) boundaryStubs.set(keys[index], ref)
      })
    }
  }
  return { rows, clips: copyClips(state), boundaryStubs, entityLookup: allById, keptRepresentatives: kept }
}

function representativeAtLevel(
  ref: RowRef,
  level: Level,
  byId: Map<string, RowRef>,
  boundaryStubs: Map<string, RowRef>,
): RowRef | null {
  const top = topRepresentative(ref, byId)
  if (top && boundaryStubs.has(nodeKey(top.kind as EntityKind, top.row.id))) return top
  if (ref.kind === 'users' || ref.kind === 'systems') return ref
  if (level === 'systems') return top
  if (level === 'subsystems') {
    return ancestorOfKind(ref, 'subsystems', byId)
      ?? ancestorOfKind(ref, 'containers', byId)
      ?? ref
  }
  if (level === 'containers') {
    return ancestorOfKind(ref, 'containers', byId) ?? ref
  }
  return ancestorOfKind(ref, 'components', byId) ?? ref
}

function graphNode(ref: RowRef, boundaryStubs: Map<string, RowRef>): GraphNode {
  const key = nodeKey(ref.kind as EntityKind, ref.row.id)
  return { key, kind: ref.kind as EntityKind, row: ref.row, boundary: boundaryStubs.has(key), members: [] }
}

export function rollUp(state: ScopedState, level: Level): RolledGraph {
  const byId = new Map(state.entityLookup)
  const nodes = new Map<string, GraphNode>()
  const ensureNode = (ref: RowRef): GraphNode => {
    const key = nodeKey(ref.kind as EntityKind, ref.row.id)
    const existing = nodes.get(key)
    if (existing) return existing
    const created = graphNode(ref, state.boundaryStubs)
    nodes.set(key, created)
    return created
  }

  const levelKind = level as EntityKind
  for (const ref of entityRows(state)) {
    if (ref.kind === levelKind || ref.kind === 'users') ensureNode(ref)
    const representative = representativeAtLevel(ref, level, byId, state.boundaryStubs)
    if (representative) ensureNode(representative).members.push(ref)
  }
  for (const ref of state.boundaryStubs.values()) ensureNode(ref)

  const edges = new Map<string, GraphEdge>()
  for (const kind of ['interfaces', 'relationships'] as const) {
    for (const row of state.rows[kind]) {
      const pair = endpoints(row)
      if (!pair) continue
      const rawLeft = byId.get(pair[0])
      const rawRight = byId.get(pair[1])
      if (!rawLeft || !rawRight) continue
      const left = representativeAtLevel(rawLeft, level, byId, state.boundaryStubs)
      const right = representativeAtLevel(rawRight, level, byId, state.boundaryStubs)
      if (!left || !right) continue
      const leftKey = nodeKey(left.kind as EntityKind, left.row.id)
      const rightKey = nodeKey(right.kind as EntityKind, right.row.id)
      if (leftKey === rightKey) continue
      const leftNode = ensureNode(left)
      const rightNode = ensureNode(right)
      if (!leftNode.members.some((member) => member.kind === rawLeft.kind && member.row.id === rawLeft.row.id)) {
        leftNode.members.push(rawLeft)
      }
      if (!rightNode.members.some((member) => member.kind === rawRight.kind && member.row.id === rawRight.row.id)) {
        rightNode.members.push(rawRight)
      }
      const [a, b] = [leftKey, rightKey].sort()
      const key = `${a}|${b}`
      if (!edges.has(key)) {
        edges.set(key, {
          key,
          a,
          b,
          interfaces: [],
          relationships: [],
          interfaceRows: [],
          relationshipRows: [],
          orientations: [],
        })
      }
      const edge = edges.get(key)!
      edge.orientations.push({ kind, id: row.id, from: leftKey, to: rightKey })
      if (kind === 'interfaces') {
        edge.interfaces.push(row.id)
        edge.interfaceRows.push(row)
      } else {
        edge.relationships.push(row.id)
        edge.relationshipRows.push(row)
      }
    }
  }
  return {
    nodes: [...nodes.values()].sort((left, right) => left.key.localeCompare(right.key)),
    edges: [...edges.values()].sort((left, right) => left.key.localeCompare(right.key)),
    boundaries: [],
    state,
  }
}

function boundaryKey(ref: RowRef): string {
  return `boundary:${nodeKey(ref.kind as EntityKind, ref.row.id)}`
}

function boundaryAncestors(ref: RowRef, level: Level, byId: Map<string, RowRef>): RowRef[] {
  if (level === 'systems') return []
  const boundaryKinds: Record<Exclude<Level, 'systems'>, Set<EntityKind>> = {
    subsystems: new Set(['systems']),
    containers: new Set(['systems', 'subsystems']),
    components: new Set(['systems', 'subsystems', 'containers']),
  }
  const ancestors: RowRef[] = []
  let cursor = parentRef(ref, byId)
  while (cursor) {
    if (boundaryKinds[level].has(cursor.kind as EntityKind)) ancestors.unshift(cursor)
    cursor = parentRef(cursor, byId)
  }
  return ancestors
}

export function withBoundaries(graph: RolledGraph, level: Level): RolledGraph {
  const boundaries = new Map<string, GraphBoundary>()
  for (const node of graph.nodes) {
    const ref = { kind: node.kind, row: node.row }
    const ancestors = boundaryAncestors(ref, level, graph.state.entityLookup)
    let parentKey: string | null = null
    for (const ancestor of ancestors) {
      const key = boundaryKey(ancestor)
      if (!boundaries.has(key)) {
        boundaries.set(key, {
          key,
          nodeKey: nodeKey(ancestor.kind as EntityKind, ancestor.row.id),
          kind: ancestor.kind as EntityKind,
          row: ancestor.row,
          parentKey,
          childKeys: [],
          stub: false,
        })
      }
      parentKey = key
    }
    if (parentKey) boundaries.get(parentKey)!.childKeys.push(node.key)
  }
  for (const boundary of boundaries.values()) {
    if (boundary.parentKey) boundaries.get(boundary.parentKey)?.childKeys.push(boundary.key)
    if (graph.edges.some((edge) => edge.a === boundary.nodeKey || edge.b === boundary.nodeKey)) {
      boundary.childKeys.push(boundary.nodeKey)
    }
  }
  const claimedEndpointNodes = new Set([...boundaries.values()].filter((boundary) => boundary.childKeys.includes(boundary.nodeKey)).map((boundary) => boundary.nodeKey))
  for (const boundary of boundaries.values()) {
    boundary.childKeys = boundary.childKeys.filter((child) => !claimedEndpointNodes.has(child) || child === boundary.nodeKey)
  }
  return { ...graph, boundaries: [...boundaries.values()].sort((left, right) => left.key.localeCompare(right.key)) }
}

function isDescendant(ref: RowRef, rootKey: string, byId: Map<string, RowRef>): boolean {
  let cursor: RowRef | null = ref
  while (cursor) {
    if (nodeKey(cursor.kind as EntityKind, cursor.row.id) === rootKey) return true
    cursor = parentRef(cursor, byId)
  }
  return false
}

function directChildRepresentative(ref: RowRef, rootKey: string, byId: Map<string, RowRef>): RowRef | null {
  let cursor: RowRef | null = ref
  let child: RowRef | null = null
  while (cursor) {
    const key = nodeKey(cursor.kind as EntityKind, cursor.row.id)
    if (key === rootKey) return child
    child = cursor
    cursor = parentRef(cursor, byId)
  }
  return null
}

export function drillAt(state: ProjectedState, rootKey: string): RolledGraph {
  const scoped = scopeAt(state, null)
  const byId = scoped.entityLookup
  const root = byId.get(rootKey)
  if (!root) return { nodes: [], edges: [], boundaries: [], state: scoped }
  const directChildren = entityRows(state).filter((ref) => parentRef(ref, byId) === root)
  const nodes = new Map(directChildren.map((ref) => {
    const node = graphNode(ref, new Map())
    node.members.push(ref)
    return [node.key, node]
  }))
  const edges = new Map<string, GraphEdge>()
  const stubs = new Map<string, RowRef>()
  for (const kind of ['interfaces', 'relationships'] as const) {
    for (const row of state.rows[kind]) {
      const pair = endpoints(row)
      if (!pair) continue
      const raw = pair.map((id) => byId.get(id))
      if (!raw[0] || !raw[1]) continue
      const inside = raw.map((ref) => isDescendant(ref!, rootKey, byId))
      if (!inside[0] && !inside[1]) continue
      const representatives = raw.map((ref, index) => {
        // null from directChildRepresentative means the endpoint IS the drilled
        // root: keep it as a leaf inside its own boundary (same carve-out as
        // withBoundaries) instead of dropping the connection.
        if (inside[index]) return directChildRepresentative(ref!, rootKey, byId) ?? root
        const top = topRepresentative(ref!, byId)
        if (top?.kind === 'systems') stubs.set(nodeKey(top.kind, top.row.id), top)
        return top
      })
      if (!representatives[0] || !representatives[1]) continue
      const leftKey = nodeKey(representatives[0]!.kind as EntityKind, representatives[0]!.row.id)
      const rightKey = nodeKey(representatives[1]!.kind as EntityKind, representatives[1]!.row.id)
      if (leftKey === rightKey) continue
      representatives.forEach((ref, index) => {
        const key = index ? rightKey : leftKey
        if (!nodes.has(key)) nodes.set(key, graphNode(ref!, stubs))
        const rawRef = raw[index]!
        if (!nodes.get(key)!.members.some((member) => member.kind === rawRef.kind && member.row.id === rawRef.row.id)) {
          nodes.get(key)!.members.push(rawRef)
        }
      })
      const [a, b] = [leftKey, rightKey].sort()
      const key = `${a}|${b}`
      if (!edges.has(key)) edges.set(key, {
        key, a, b, interfaces: [], relationships: [], interfaceRows: [], relationshipRows: [], orientations: [],
      })
      const edge = edges.get(key)!
      edge.orientations.push({ kind, id: row.id, from: leftKey, to: rightKey })
      if (kind === 'interfaces') { edge.interfaces.push(row.id); edge.interfaceRows.push(row) }
      else { edge.relationships.push(row.id); edge.relationshipRows.push(row) }
    }
  }
  const rootBoundary: GraphBoundary = {
    key: boundaryKey(root),
    nodeKey: rootKey,
    kind: root.kind as EntityKind,
    row: root.row,
    parentKey: null,
    childKeys: [
      ...directChildren.map((ref) => nodeKey(ref.kind as EntityKind, ref.row.id)),
      ...(nodes.has(rootKey) ? [rootKey] : []),
    ],
    stub: false,
  }
  const stubBoundaries = [...stubs.entries()].map(([key, ref]): GraphBoundary => ({
    key: boundaryKey(ref), nodeKey: key, kind: ref.kind as EntityKind, row: ref.row,
    parentKey: null, childKeys: [], stub: true,
  }))
  return {
    nodes: [...nodes.values()].sort((left, right) => left.key.localeCompare(right.key)),
    edges: [...edges.values()].sort((left, right) => left.key.localeCompare(right.key)),
    boundaries: [rootBoundary, ...stubBoundaries],
    state: { ...scoped, boundaryStubs: stubs },
  }
}

export function legendEntries(graph: RolledGraph): Array<{ tag: string; count: number }> {
  const counts = new Map<string, number>()
  for (const node of graph.nodes) {
    const tags = new Set([...(node.row.tags ?? []), ...node.members.flatMap((member) => member.row.tags ?? [])])
    for (const tag of tags) counts.set(tag, (counts.get(tag) ?? 0) + 1)
  }
  return [...counts].sort(([left], [right]) => left.localeCompare(right)).map(([tag, count]) => ({ tag, count }))
}

function everLiveState(payload: ReportPayload, timeline: number): ProjectedState {
  const rows = emptyRows()
  for (const kind of KINDS) {
    const seen = new Set<string>()
    for (const row of payload.rows[kind]) {
      if (seen.has(row.id) || !(row.intervals[timeline]?.live.length)) continue
      seen.add(row.id)
      rows[kind].push(row)
    }
  }
  return { rows, clips: emptyClips() }
}

export function unionGraph(payload: ReportPayload, timeline: number, level: Level, drill: string | null = null): RolledGraph {
  const state = everLiveState(payload, timeline)
  return drill ? drillAt(state, drill) : withBoundaries(rollUp(scopeAt(state, null), level), level)
}

export function projectState(payload: ReportPayload, view: View): ProjectedView {
  const rawState = stateAt(payload, view.timeline, view.position)
  const graph = view.drill
    ? drillAt(rawState, view.drill)
    : withBoundaries(rollUp(scopeAt(rawState, view.scope), view.level), view.level)
  return { ...graph, rawState }
}

export function affectedKeys(diff: StateDiff): Set<string> {
  return new Set([
    ...diff.added.map((item) => `${item.kind}:${item.id}`),
    ...diff.removed.map((item) => `${item.kind}:${item.id}`),
    ...diff.changed.map((item) => `${item.kind}:${item.id}`),
  ])
}

export function isEntityKind(kind: RowKind): kind is EntityKind {
  return ENTITY_KIND_SET.has(kind)
}
