import type {
  PreparedSolutionSnapshots,
  SolutionSelectionIndexes,
  ViewGraph,
  ViewGraphEdge,
  ViewGraphNode,
} from '../../src/data/types'

const SYSTEM_COUNT = 180
const SNAPSHOT_COUNT = 3

function nodes(order: number): ViewGraphNode[] {
  return Array.from({ length: SYSTEM_COUNT }, (_, index) => ({
    id: `system-${index.toString().padStart(3, '0')}`,
    entity_kind: 'system',
    name: `System ${index}`,
    children: [],
    status: order > 0 && index % 17 === 0 ? 'Changed' : 'No Change',
    context_status: order > 0 && index % 17 === 0 ? 'change' : 'no_change',
    tombstone: false,
    future: false,
    tags: [`tag-${index % 9}`],
    groups: [`group-${index % 12}`],
    related_changes: index % 17 === 0 ? [`change-${order}`] : [],
    properties: { owner: `team-${index % 18}` },
  }))
}

function edges(): ViewGraphEdge[] {
  return Array.from({ length: SYSTEM_COUNT * 2 }, (_, index) => {
    const source = index % SYSTEM_COUNT
    const step = index < SYSTEM_COUNT ? 1 : 7
    const target = (source + step) % SYSTEM_COUNT
    return {
      id: `interface-${index.toString().padStart(3, '0')}`,
      entity_kind: 'interface',
      name: `Interface ${index}`,
      source_id: `system-${source.toString().padStart(3, '0')}`,
      target_id: `system-${target.toString().padStart(3, '0')}`,
      direction: 'provider_to_consumer',
      integration_type: index % 2 === 0 ? 'api' : 'event',
      status: 'No Change',
      context_status: 'no_change',
      tombstone: false,
      future: false,
      tags: [`tag-${index % 9}`],
      interface_ids: [`interface-${index.toString().padStart(3, '0')}`],
      related_changes: [],
      properties: {},
    }
  })
}

function indexes(): SolutionSelectionIndexes {
  const systems = Array.from(
    { length: SYSTEM_COUNT },
    (_, index) => `system-${index.toString().padStart(3, '0')}`,
  )
  const byModulo = (modulo: number, prefix: string) =>
    Object.fromEntries(
      Array.from({ length: modulo }, (_, value) => [
        `${prefix}-${value}`,
        systems.filter((_, index) => index % modulo === value),
      ]),
    )
  return {
    systems,
    system_groups: byModulo(12, 'group'),
    changes: byModulo(6, 'change'),
    change_groups: byModulo(3, 'wave'),
    change_impacts: {},
    change_group_impacts: {},
    tags: byModulo(9, 'tag'),
  }
}

function graph(order: number): ViewGraph {
  const id = `benchmark-snapshot-${order}`
  return {
    id,
    selection: {
      id: `selection-${id}`,
      state_id: id,
      roadmap_id: 'benchmark-roadmap',
      order,
      selection: {
        roadmap: 'benchmark-roadmap',
        order,
        display_statuses: [],
        system_set: { systems: [], system_groups: [], changes: [], change_groups: [], tags: [] },
        interface_depth: 0,
        level: 'system',
        color_by: 'change_status',
        theme: 'clean',
      },
    },
    resolved_state: { id },
    nodes: nodes(order),
    containers: [],
    edges: edges(),
    changes: [],
    focus: [],
    focus_overrides: [],
    diagram_ids: [],
    hints: {},
  }
}

export function projectionBenchmarkFixture(): PreparedSolutionSnapshots {
  const orders = Array.from({ length: SNAPSHOT_COUNT }, (_, order) => order)
  const selectionIndexes = indexes()
  return {
    roadmap_id: 'benchmark-roadmap',
    snapshots: Object.fromEntries(orders.map((order) => [String(order), graph(order)])),
    indexes: Object.fromEntries(orders.map((order) => [String(order), selectionIndexes])),
    system_presence: Object.fromEntries(selectionIndexes.systems.map((id) => [id, orders])),
    unavailable_orders: [],
  }
}
