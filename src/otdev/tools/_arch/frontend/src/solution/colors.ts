import type {
  ColorBy,
  ElementStyle,
  PresentationConfig,
  ViewGraph,
  ViewGraphEdge,
  ViewGraphNode,
} from '../data/types'

function statusName(status: string): 'no_change' | 'changed' | 'added' | 'removed' {
  if (status === 'Changed') return 'changed'
  if (status === 'Added') return 'added'
  if (status === 'Removed') return 'removed'
  return 'no_change'
}

function mergeStyles(...styles: (ElementStyle | undefined)[]): ElementStyle {
  return Object.assign({}, ...styles.filter(Boolean))
}

function themeFor(graph: ViewGraph, presentation: PresentationConfig) {
  const id = graph.selection.selection.theme ?? presentation.default_theme
  return presentation.resolved_themes[id] ?? presentation.resolved_themes.clean
}

function statusStyle(
  kind: ViewGraphNode['entity_kind'] | ViewGraphEdge['entity_kind'],
  contextStatus: ViewGraphNode['context_status'],
  status: ViewGraphNode['status'],
  colorBy: ColorBy,
  presentation: PresentationConfig,
  theme: ReturnType<typeof themeFor>,
): ElementStyle | undefined {
  if (colorBy !== 'change_status') return kind === 'user' ? theme?.statuses[contextStatus] : undefined
  if (kind === 'user' || kind === 'relationship') return theme?.statuses[contextStatus]
  return presentation.palettes.change_status[kind][statusName(status)]
}

function nodeStyle(
  node: ViewGraphNode,
  colorBy: ColorBy,
  presentation: PresentationConfig,
  theme: ReturnType<typeof themeFor>,
): ElementStyle {
  const themeTags = node.tags.map((tag) => theme?.elements[`tag:${tag}`])
  const tagColor =
    colorBy === 'tag'
      ? node.tags.map((tag) => presentation.palettes.tag[tag]).find(Boolean)
      : undefined
  return mergeStyles(
    theme?.elements[node.entity_kind],
    ...themeTags,
    statusStyle(
      node.entity_kind,
      node.context_status,
      node.status,
      colorBy,
      presentation,
      theme,
    ),
    tagColor,
    theme?.elements[`entity:${node.id}`],
    node.style,
  )
}

function edgeStyle(
  edge: ViewGraphEdge,
  colorBy: ColorBy,
  presentation: PresentationConfig,
  theme: ReturnType<typeof themeFor>,
): ElementStyle {
  const integrationColor =
    colorBy === 'integration_type' && edge.integration_type
      ? presentation.palettes.integration_type[edge.integration_type]
      : undefined
  const tagColor =
    colorBy === 'tag'
      ? edge.tags.map((tag) => presentation.palettes.tag[tag]).find(Boolean)
      : undefined
  return mergeStyles(
    theme?.elements[edge.entity_kind],
    statusStyle(
      edge.entity_kind,
      edge.context_status,
      edge.status,
      colorBy,
      presentation,
      theme,
    ),
    integrationColor,
    tagColor,
    theme?.elements[`entity:${edge.id}`],
    edge.style,
  )
}

function borderColor(style: ElementStyle): string | undefined {
  const candidate = style.border?.split(/\s+/, 1)[0]
  return candidate?.startsWith('#') ? candidate : style.color
}

export function solutionColors(
  graph: ViewGraph,
  colorBy: ColorBy,
  presentation: PresentationConfig,
): {
  nodeColors: Map<string, string>
  nodeBorders: Map<string, string>
  edgeColors: Map<string, string>
} {
  const theme = themeFor(graph, presentation)
  const nodeStyles = new Map(
    graph.nodes.map((node) => [node.id, nodeStyle(node, colorBy, presentation, theme)]),
  )
  const nodeColors = new Map(
    graph.nodes.map((node) => [node.id, nodeStyles.get(node.id)?.color ?? '#f8fafc']),
  )
  const nodeBorders = new Map(
    graph.nodes.map((node) => [
      node.id,
      borderColor({ border: nodeStyles.get(node.id)?.border }) ?? '#64748b',
    ]),
  )
  const edgeColors = new Map(
    graph.edges.map((edge) => [
      edge.id,
      borderColor(edgeStyle(edge, colorBy, presentation, theme)) ?? '#64748b',
    ]),
  )
  return { nodeColors, nodeBorders, edgeColors }
}
