import {
  ENTITY_KINDS,
  KINDS,
  type EntityKind,
  type FieldChange,
  type GraphBoundary,
  type GraphEdge,
  type GraphNode,
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

function graphNode(ref: RowRef, boundaryStubs: Map<string, RowRef>): GraphNode {
  const key = nodeKey(ref.kind as EntityKind, ref.row.id)
  return { key, kind: ref.kind as EntityKind, row: ref.row, boundary: boundaryStubs.has(key), members: [] }
}

function descendants(ref: RowRef, children: Map<string, RowRef[]>): RowRef[] {
  const key = nodeKey(ref.kind as EntityKind, ref.row.id)
  return [ref, ...(children.get(key) ?? []).flatMap((child) => descendants(child, children))]
}

export function mapGraph(state: ScopedState, expansion: readonly string[]): RolledGraph {
  const byId = state.entityLookup
  const expanded = new Set(expansion)
  const children = new Map<string, RowRef[]>()
  for (const ref of entityRows(state)) {
    const parent = parentRef(ref, byId)
    if (!parent) continue
    const key = nodeKey(parent.kind as EntityKind, parent.row.id)
    children.set(key, [...(children.get(key) ?? []), ref])
  }
  for (const refs of children.values()) refs.sort((left, right) => nodeKey(left.kind as EntityKind, left.row.id).localeCompare(nodeKey(right.kind as EntityKind, right.row.id)))

  const nodes = new Map<string, GraphNode>()
  const boundaries = new Map<string, GraphBoundary>()
  const render = (ref: RowRef, parentKey: string | null): string => {
    const key = nodeKey(ref.kind as EntityKind, ref.row.id)
    const liveChildren = children.get(key) ?? []
    if (expanded.has(key) && liveChildren.length) {
      const boundary: GraphBoundary = {
        key,
        nodeKey: key,
        kind: ref.kind as EntityKind,
        row: ref.row,
        parentKey,
        childKeys: [],
        stub: false,
      }
      boundaries.set(key, boundary)
      boundary.childKeys = liveChildren.map((child) => render(child, key))
    } else {
      const node = graphNode(ref, state.boundaryStubs)
      node.members = descendants(ref, children)
      nodes.set(key, node)
    }
    return key
  }

  for (const ref of entityRows(state)) {
    if (!parentRef(ref, byId) && state.keptRepresentatives.has(nodeKey(ref.kind as EntityKind, ref.row.id))) render(ref, null)
  }
  for (const [key, ref] of state.boundaryStubs) {
    if (!nodes.has(key)) nodes.set(key, graphNode(ref, state.boundaryStubs))
  }

  const visible = new Set([...nodes.keys(), ...boundaries.keys()])
  const resolve = (ref: RowRef): string | null => {
    let cursor: RowRef | null = ref
    while (cursor) {
      const key = nodeKey(cursor.kind as EntityKind, cursor.row.id)
      if (visible.has(key)) return key
      cursor = parentRef(cursor, byId)
    }
    return null
  }
  const edges = new Map<string, GraphEdge>()
  for (const kind of ['interfaces', 'relationships'] as const) {
    for (const row of state.rows[kind]) {
      const pair = endpoints(row)
      if (!pair) continue
      const rawLeft = byId.get(pair[0])
      const rawRight = byId.get(pair[1])
      if (!rawLeft || !rawRight) continue
      const leftKey = resolve(rawLeft)
      const rightKey = resolve(rawRight)
      if (!leftKey || !rightKey || leftKey === rightKey) continue
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
  return {
    nodes: [...nodes.values()].sort((left, right) => left.key.localeCompare(right.key)),
    edges: [...edges.values()].sort((left, right) => left.key.localeCompare(right.key)),
    boundaries: [...boundaries.values()].sort((left, right) => left.key.localeCompare(right.key)),
    state,
  }
}

export function legendEntries(graph: RolledGraph): Array<{ tag: string; count: number }> {
  const counts = new Map<string, number>()
  const visible = [
    ...graph.nodes.map((node) => ({ row: node.row, members: node.members })),
    ...graph.boundaries.filter((boundary) => !boundary.stub).map((boundary) => ({ row: boundary.row, members: [{ kind: boundary.kind, row: boundary.row }] })),
  ]
  for (const node of visible) {
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

export function unionGraph(payload: ReportPayload, timeline: number, expansion: readonly string[]): RolledGraph {
  const state = everLiveState(payload, timeline)
  return mapGraph(scopeAt(state, null), expansion)
}

// Removed entities render as ghosts for the diff story. A removed expanded
// container must merge as a ghost BOUNDARY, not vanish: its ghost children
// keep their layout parent, otherwise applyPositions drops the parentId and
// stacks them at the boundary-relative origin.
export function mergeRemovedBoundaries(
  current: readonly GraphBoundary[],
  compared: readonly GraphBoundary[] | null,
  removedKeys: ReadonlySet<string>,
): Array<{ boundary: GraphBoundary; ghost: boolean }> {
  const merged = new Map(current.map((boundary) => [boundary.key, { boundary, ghost: false }]))
  for (const boundary of compared ?? []) {
    if (!merged.has(boundary.key) && !boundary.stub && removedKeys.has(boundary.key)) {
      merged.set(boundary.key, { boundary, ghost: true })
    }
  }
  return [...merged.values()]
}

export function projectState(payload: ReportPayload, view: View): ProjectedView {
  const rawState = stateAt(payload, view.timeline, view.position)
  const graph = mapGraph(scopeAt(rawState, view.scope), view.expand)
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
