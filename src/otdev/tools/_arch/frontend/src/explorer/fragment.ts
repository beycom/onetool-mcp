import type {
  ArchitectureLevel,
  BrowseGroup,
  ColorBy,
  ContextStatus,
  SystemSetSelector,
} from '../data/types'

export interface FragmentState {
  graph?: string
  compare?: string
  browse?: BrowseGroup
  subject?: string
  order?: number
  depth?: number
  level?: ArchitectureLevel
  colorBy?: ColorBy
  visibility?: string
  statuses?: ContextStatus[]
  search?: string
  diagram?: string
  selected?: string
  dataOpen?: boolean
  inspectorOpen?: boolean
  activeTable?: 'elements' | 'included_interfaces' | 'boundary_interfaces'
  systemSet?: SystemSetSelector
}

const BROWSE_GROUPS = new Set<BrowseGroup>([
  'system',
  'system_group',
  'change',
  'change_group',
  'tag',
])
const LEVELS = new Set<ArchitectureLevel>(['system', 'application', 'component'])
const COLOR_MODES = new Set<ColorBy>(['change_status', 'integration_type', 'tag'])
const STATUSES = new Set<ContextStatus>([
  'out_of_scope',
  'future',
  'new',
  'change',
  'no_change',
  'decommission',
])
const TABLES = new Set(['elements', 'included_interfaces', 'boundary_interfaces'])

function nonNegativeInteger(value: string | null): number | undefined {
  if (value === null || value.trim() === '') return undefined
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : undefined
}

function stringList(value: string | null): string[] | undefined {
  if (value === null) return undefined
  try {
    const parsed = JSON.parse(value) as unknown
    if (!Array.isArray(parsed) || !parsed.every((item) => typeof item === 'string' && item))
      return undefined
    return parsed
  } catch {
    return undefined
  }
}

export function parseFragment(hash: string): FragmentState {
  const params = new URLSearchParams(hash.replace(/^#/, ''))
  const browse = params.get('browse')
  const level = params.get('level')
  const colorBy = params.get('colorBy')
  const activeTable = params.get('table')
  const statuses = (params.get('statuses') ?? '')
    .split(',')
    .filter((status): status is ContextStatus => STATUSES.has(status as ContextStatus))
  const selectorValues = {
    systems: stringList(params.get('systems')),
    system_groups: stringList(params.get('systemGroups')),
    changes: stringList(params.get('changes')),
    change_groups: stringList(params.get('changeGroups')),
    tags: stringList(params.get('tags')),
  }
  const systemSet = Object.values(selectorValues).some((value) => value !== undefined)
    ? {
        systems: selectorValues.systems ?? [],
        system_groups: selectorValues.system_groups ?? [],
        changes: selectorValues.changes ?? [],
        change_groups: selectorValues.change_groups ?? [],
        tags: selectorValues.tags ?? [],
      }
    : undefined
  const result: FragmentState = {
    graph: params.get('graph') ?? undefined,
    compare: params.get('compare') ?? undefined,
    browse:
      browse !== null && BROWSE_GROUPS.has(browse as BrowseGroup)
        ? (browse as BrowseGroup)
        : undefined,
    subject: params.get('subject') ?? undefined,
    order: nonNegativeInteger(params.get('order')),
    depth: nonNegativeInteger(params.get('depth')),
    level: level !== null && LEVELS.has(level as ArchitectureLevel) ? (level as ArchitectureLevel) : undefined,
    colorBy: colorBy !== null && COLOR_MODES.has(colorBy as ColorBy) ? (colorBy as ColorBy) : undefined,
    visibility: params.get('visibility') ?? undefined,
    statuses: statuses.length > 0 ? statuses : undefined,
    search: params.get('search') ?? undefined,
    diagram: params.get('diagram') ?? undefined,
    selected: params.get('selected') ?? undefined,
    dataOpen: params.get('data') === '1' ? true : undefined,
    inspectorOpen: params.get('details') === '1' ? true : undefined,
    activeTable:
      activeTable !== null && TABLES.has(activeTable)
        ? (activeTable as FragmentState['activeTable'])
        : undefined,
    systemSet,
  }
  return Object.fromEntries(
    Object.entries(result).filter((entry) => entry[1] !== undefined),
  ) as FragmentState
}

export function serializeFragment(state: FragmentState): string {
  const params = new URLSearchParams()
  const entries: [string, string | undefined][] = [
    ['graph', state.graph],
    ['compare', state.compare],
    ['browse', state.browse],
    ['subject', state.subject],
    ['order', state.order?.toString()],
    ['depth', state.depth?.toString()],
    ['level', state.level],
    ['colorBy', state.colorBy],
    ['visibility', state.visibility],
    ['statuses', state.statuses?.join(',')],
    ['search', state.search],
    ['diagram', state.diagram],
    ['selected', state.selected],
    ['data', state.dataOpen ? '1' : undefined],
    ['details', state.inspectorOpen ? '1' : undefined],
    ['table', state.activeTable],
    ['systems', state.systemSet?.systems.length ? JSON.stringify(state.systemSet.systems) : undefined],
    [
      'systemGroups',
      state.systemSet?.system_groups.length
        ? JSON.stringify(state.systemSet.system_groups)
        : undefined,
    ],
    ['changes', state.systemSet?.changes.length ? JSON.stringify(state.systemSet.changes) : undefined],
    [
      'changeGroups',
      state.systemSet?.change_groups.length
        ? JSON.stringify(state.systemSet.change_groups)
        : undefined,
    ],
    ['tags', state.systemSet?.tags.length ? JSON.stringify(state.systemSet.tags) : undefined],
  ]
  for (const [key, value] of entries) {
    if (value) params.set(key, value)
  }
  return `#${params.toString()}`
}
