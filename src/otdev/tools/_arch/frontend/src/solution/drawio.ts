import type { ViewGraph, ViewGraphEdge, ViewGraphNode } from '../data/types'
import type { SolutionLayoutResult } from './renderer/types'

const MODIFIED = '2026-01-01T00:00:00.000Z'

function escape(value: unknown): string {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;')
}

function attributes(values: Record<string, unknown>): string {
  return Object.entries(values)
    .filter(([, value]) => value !== undefined)
    .map(([name, value]) => `${name}="${escape(value)}"`)
    .join(' ')
}

function stableHash(value: string): string {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

function titleCase(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase())
}

export function drawioPageName(graph: ViewGraph): string {
  const selection = graph.selection.selection
  const order = graph.selection.order
  const snapshotChange = graph.changes.find((change) => change.order === order)
  const snapshot =
    order === 0
      ? 'Base'
      : snapshotChange?.name ??
        (order !== undefined ? `Order ${order}` : (selection.state ?? graph.selection.state_id))

  let scope: string | undefined
  if (selection.subject) {
    let subject = selection.subject
    if (selection.browse_by === 'system') {
      subject =
        graph.nodes.find((node) => node.id === subject && node.entity_kind === 'system')?.name ??
        subject
    } else if (selection.browse_by === 'change') {
      subject = graph.changes.find((change) => change.id === subject)?.name ?? subject
    }
    if (!(selection.browse_by === 'change' && subject === snapshot)) {
      scope = `${titleCase(selection.browse_by ?? 'scope')}: ${subject}`
    }
  } else {
    const selected = [
      ...selection.system_set.systems.map((value) => `System: ${value}`),
      ...selection.system_set.system_groups.map((value) => `System group: ${value}`),
      ...selection.system_set.changes.map((value) => `Change: ${value}`),
      ...selection.system_set.change_groups.map((value) => `Change group: ${value}`),
      ...selection.system_set.tags.map((value) => `Tag: ${value}`),
    ]
    scope = selected.length > 0 ? selected.join(' + ') : 'All systems'
  }
  return [
    snapshot,
    ...(scope ? [scope] : []),
    titleCase(selection.level),
    `depth ${selection.interface_depth}`,
  ].join(' · ')
}

function nodeStyle(node: ViewGraphNode, color: string, border: string): string {
  const removed = node.status === 'Removed' ? 'dashed=1;strokeWidth=2;' : ''
  return `rounded=1;whiteSpace=wrap;html=1;fillColor=${color};strokeColor=${border};${removed}`
}

function edgeStyle(edge: ViewGraphEdge, color: string): string {
  const arrows =
    edge.direction === 'consumer_to_provider' || edge.direction === 'reverse'
      ? 'startArrow=block;endArrow=none;'
      : edge.direction === 'bidirectional'
        ? 'startArrow=block;endArrow=block;'
        : 'startArrow=none;endArrow=block;'
  const removed = edge.status === 'Removed' ? 'dashed=1;strokeWidth=2;' : ''
  return `edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor=${color};${arrows}${removed}`
}

export function drawioXml({
  graph,
  layout,
  nodeColors,
  nodeBorders,
  edgeColors,
  pageName,
}: {
  graph: ViewGraph
  layout: SolutionLayoutResult
  nodeColors: ReadonlyMap<string, string>
  nodeBorders: ReadonlyMap<string, string>
  edgeColors: ReadonlyMap<string, string>
  pageName: string
}): string {
  if (layout.graphId !== graph.id) throw new Error('Layout does not match the active solution')
  if (layout.selectionId !== graph.selection.id)
    throw new Error('Layout does not match the active selection')
  const nodes = new Map(graph.nodes.map((node) => [node.id, node]))
  const edges = new Map(graph.edges.map((edge) => [edge.id, edge]))
  const layoutNodes = new Map(layout.nodes.map((node) => [node.id, node]))
  const lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    `<mxfile ${attributes({ host: 'OneTool', modified: MODIFIED, agent: 'OneTool architecture explorer', version: '1', type: 'device', compressed: 'false' })}>`,
    `  <diagram ${attributes({ id: stableHash(graph.selection.id), name: pageName, selectionId: graph.selection.id, viewGraphId: graph.id, snapshotId: graph.selection.state_id, selection: JSON.stringify(graph.selection.selection) })}>`,
    `    <mxGraphModel ${attributes({ dx: 0, dy: 0, grid: 1, gridSize: 10, page: 1, pageScale: 1, pageWidth: layout.bounds.width, pageHeight: layout.bounds.height })}>`,
    '      <root>',
    '        <mxCell id="0"/>',
    '        <mxCell id="1" parent="0"/>',
  ]
  for (const item of [...layout.nodes].sort((left, right) => left.id.localeCompare(right.id))) {
    const node = nodes.get(item.id)
    if (!node) continue
    const parent = item.parent && layoutNodes.has(item.parent) ? item.parent : '1'
    const parentBounds = parent === '1' ? undefined : layoutNodes.get(parent)?.bounds
    lines.push(
      `        <mxCell ${attributes({ id: node.id, value: node.name, style: nodeStyle(node, nodeColors.get(node.id) ?? '#f8fafc', nodeBorders.get(node.id) ?? '#64748b'), vertex: 1, parent, canonicalId: node.id, kind: node.entity_kind, status: node.status, selectionId: graph.selection.id })}>`,
      `          <mxGeometry ${attributes({ x: item.bounds.x - (parentBounds?.x ?? 0), y: item.bounds.y - (parentBounds?.y ?? 0), width: item.bounds.width, height: item.bounds.height, as: 'geometry' })}/>`,
      '        </mxCell>',
    )
  }
  for (const item of [...layout.edges].sort((left, right) => left.id.localeCompare(right.id))) {
    const edge = edges.get(item.id)
    if (!edge) continue
    lines.push(
      `        <mxCell ${attributes({ id: edge.id, value: edge.name, style: edgeStyle(edge, edgeColors.get(edge.id) ?? '#64748b'), edge: 1, parent: 1, source: item.source, target: item.target, canonicalId: edge.id, interfaceIds: item.interfaceIds.join(','), kind: edge.entity_kind, status: edge.status, selectionId: graph.selection.id })}>`,
      '          <mxGeometry relative="1" as="geometry">',
      '            <Array as="points">',
      ...item.route.map((point) => `              <mxPoint x="${point.x}" y="${point.y}"/>`),
      '            </Array>',
      '          </mxGeometry>',
      '        </mxCell>',
    )
  }
  lines.push('      </root>', '    </mxGraphModel>', '  </diagram>', '</mxfile>')
  return lines.join('\n')
}

function slug(value: string): string {
  return value.toLowerCase().replaceAll(/[^a-z0-9]+/g, '-').replaceAll(/^-|-$/g, '') || 'solution'
}

export function drawioFilename(graph: ViewGraph): string {
  const selection = graph.selection.selection
  const selector = selection.system_set
  const values = [
    ...selector.systems,
    ...selector.system_groups,
    ...selector.changes,
    ...selector.change_groups,
    ...selector.tags,
  ]
  const source = graph.resolved_state.id.split('@')[0]!
  const scope = values.length > 0 ? values.join('-') : 'all'
  const snapshot = `${graph.selection.roadmap_id ?? 'state'}-${graph.selection.order ?? 0}`
  return `${slug(source)}-${slug(scope)}-${slug(snapshot)}-n${selection.interface_depth}-${selection.level}.drawio`
}

export function downloadDrawio(filename: string, content: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: 'application/vnd.jgraph.mxfile' }))
  const anchor = document.createElement('a')
  anchor.download = filename
  anchor.href = url
  anchor.click()
  URL.revokeObjectURL(url)
}
