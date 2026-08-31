// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react'
import type { CSSProperties, ReactNode } from 'react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('@xyflow/react', () => ({
  BaseEdge: ({ className, id, style }: { className?: string; id: string; style?: CSSProperties }) => <path className={className} data-testid={id} style={style} />,
  EdgeLabelRenderer: ({ children }: { children: ReactNode }) => children,
  Handle: ({ position, type }: { position: string; type: string }) => <span data-position={position} data-type={type} />,
  MiniMap: () => null,
  Position: { Left: 'left', Right: 'right' },
  ReactFlow: () => null,
}))

import { ArchitectureNodeView, BoundaryNodeView, SemanticEdge } from './App'
import { edgeLabelVisible, portLabelPlacement, splitEdgeDirections, type EdgeEmphasis } from './edgePresentation'
import { dataKindChip } from './GridPanel'
import { DEFAULT_KIND_COLORS, themeStyle } from './theme'
import type { GraphEdge, ReportRow } from './types'

afterEach(cleanup)

test('boundary collapse control follows the title inside the header with collapse semantics', () => {
  const { container } = render(BoundaryNodeView({
    data: {
      boundary: {
        childKeys: ['containers:child'], key: 'systems:parent', kind: 'systems', nodeKey: 'systems:parent',
        parentKey: null, row: { id: 'parent', intervals: [], name: 'Parent' }, stub: false,
      },
      description: '',
      ghost: false,
      label: 'Parent',
      onCollapse: () => undefined,
    },
    selected: false,
  } as never))

  const header = container.querySelector('header')!
  const title = header.querySelector<HTMLElement>('.boundary-title')!
  const collapse = screen.getByRole('button', { name: 'Collapse Parent' })
  Object.defineProperty(title, 'getBoundingClientRect', { value: () => ({ bottom: 36, height: 24, left: 10, right: 150, top: 12, width: 140, x: 10, y: 12, toJSON: () => ({}) }) })
  Object.defineProperty(collapse, 'getBoundingClientRect', { value: () => ({ bottom: 38, height: 28, left: 157, right: 185, top: 10, width: 28, x: 157, y: 10, toJSON: () => ({}) }) })

  expect(title.nextElementSibling).toBe(collapse)
  expect(collapse.getBoundingClientRect().left - title.getBoundingClientRect().right).toBe(7)
  expect(collapse.textContent).not.toBe('×')
  expect(container.querySelector('[data-type="target"][data-position="left"]')).toBeTruthy()
  expect(container.querySelector('[data-type="source"][data-position="right"]')).toBeTruthy()
})

function relationship(id: string, action: string): ReportRow {
  return { action, id, intervals: [], source: 'systems:hub', target: 'systems:peer' }
}

function graphEdge(rows: ReportRow[]): GraphEdge {
  return {
    a: 'systems:hub',
    b: 'systems:peer',
    interfaceRows: [],
    interfaces: [],
    key: 'systems:hub|systems:peer',
    orientations: rows.map((row) => ({ from: 'systems:hub', id: row.id, kind: 'relationships', to: 'systems:peer' })),
    relationshipRows: rows,
    relationships: rows.map((row) => row.id),
  }
}

function edgeElement(edge: GraphEdge, memberCount: number, emphasis: EdgeEmphasis | 'selected', showLabel: boolean, id = 'spline', hovered = false) {
  const spline = splitEdgeDirections(edge, 'ownership')[0]
  return SemanticEdge({
    data: {
      anchors: {
        sourcePoint: { side: 'right', x: 10, y: 20 },
        targetPoint: { side: 'left', x: 90, y: 20 },
      },
      direction: 'forward',
      edge,
      emphasis,
      hovered,
      label: spline.label,
      labelPoint: { x: 50, y: 20 },
      memberCount,
      onHover: () => undefined,
      onSelect: () => undefined,
      path: 'M 10 20 L 90 20',
      port: null,
      selected: emphasis === 'selected',
      showLabel,
      statuses: [],
    },
    id,
  } as never)
}

test('port labels offset outward from their anchor side and clear the card edge', () => {
  const right = portLabelPlacement({ count: 1, label: 'Authorize and capture payment', point: { x: 340, y: 150, side: 'right' } })
  expect(right.rect.x).toBeGreaterThan(340)
  expect(right.point.x).toBeGreaterThan(340)
  const top = portLabelPlacement({ count: 2, label: 'Query stock', point: { x: 200, y: 100, side: 'top' } })
  expect(top.rect.y + top.rect.height).toBeLessThan(100)
  const left = portLabelPlacement({ count: 1, label: 'Fetch rates', point: { x: 100, y: 150, side: 'left' } })
  expect(left.rect.x + left.rect.width).toBeLessThan(100)
  const bottom = portLabelPlacement({ count: 1, label: 'Emit events', point: { x: 200, y: 262, side: 'bottom' } })
  expect(bottom.rect.y).toBeGreaterThan(262)
})

test('a collision-cleared port renders its label at the offset point and a collision-hidden one stays a dot', () => {
  const edge = graphEdge([relationship('rates', 'Fetch rates')])
  const spline = splitEdgeDirections(edge, 'ownership')[0]
  const port = { count: 1, label: 'Fetch rates', point: { x: 10, y: 20, side: 'right' } }
  const base = {
    anchors: { sourcePoint: { x: 0, y: 0, side: 'right' }, targetPoint: { x: 100, y: 0, side: 'left' } },
    direction: 'forward', edge, emphasis: 'normal', hovered: false, label: spline.label,
    labelPoint: { x: 50, y: 20 }, memberCount: 1, onHover: () => undefined, onSelect: () => undefined,
    path: 'M 0 0 L 100 0', selected: false, showLabel: false, statuses: [], port,
  }
  const { rerender } = render(SemanticEdge({ data: { ...base, portLabel: { x: 60, y: 20 } }, id: 'port-a' } as never))
  const expanded = screen.getByRole('button', { name: 'Interface port Fetch rates' })
  expect(expanded.dataset.expanded).toBe('true')
  expect(expanded.textContent).toContain('Fetch rates')
  expect(expanded.style.transform).toContain('translate(60px,20px)')

  rerender(SemanticEdge({ data: { ...base, portLabel: null }, id: 'port-a' } as never))
  const dot = screen.getByRole('button', { name: 'Interface port Fetch rates' })
  expect(dot.dataset.expanded).toBe('false')
  expect(dot.textContent).toBe('')
  expect(dot.style.transform).toContain('translate(10px,20px)')
})

test('hovering a spline whose collision-hidden pill reveals exactly that pill', () => {
  const hidden = graphEdge([relationship('hidden', 'Hidden collision')])
  const other = graphEdge([relationship('other', 'Other collision')])
  const { container, rerender } = render(<>{edgeElement(hidden, 1, 'normal', false, 'hidden')}{edgeElement(other, 1, 'normal', false, 'other')}</>)

  expect(container.querySelectorAll('.edge-label')).toHaveLength(0)
  rerender(<>{edgeElement(hidden, 1, 'selected', true, 'hidden', true)}{edgeElement(other, 1, 'unrelated', false, 'other')}</>)
  expect(container.querySelectorAll('.edge-label')).toHaveLength(1)
  expect(screen.getByRole('button', { name: 'Hidden collision' })).toBeTruthy()
})

test('prescribed #3 renders single and aggregated labels at Read but hides neutral labels at Far', () => {
  const single = graphEdge([relationship('calls', 'Calls catalog')])
  const aggregate = graphEdge([relationship('publishes', 'Publishes orders'), relationship('audits', 'Audits orders')])
  const { container, rerender } = render(edgeElement(single, 1, 'normal', edgeLabelVisible('read', false, false)))

  expect(screen.getByRole('button', { name: 'Calls catalog' }).getAttribute('title')).toBe('Calls catalog')
  expect(container.querySelector('.edge-label i')).toBeNull()

  rerender(edgeElement(aggregate, 2, 'normal', edgeLabelVisible('read', false, false)))
  expect(screen.getByRole('button', { name: 'Publishes orders2' }).getAttribute('title')).toBe('Publishes orders')
  expect(container.querySelector('.edge-label i')?.textContent).toBe('2')

  rerender(edgeElement(single, 1, 'normal', edgeLabelVisible('far', false, false)))
  expect(container.querySelector('.edge-label')).toBeNull()
})

test('prescribed #5 applies a partial theme override while retaining default kind custom properties', () => {
  render(<div data-testid="theme" style={themeStyle({ kinds: { system: '#123456' } })} />)
  const style = screen.getByTestId('theme').style

  expect(style.getPropertyValue('--kind-system')).toBe('#123456')
  expect(style.getPropertyValue('--kind-subsystem')).toBe(DEFAULT_KIND_COLORS.subsystem)
  expect(style.getPropertyValue('--kind-user')).toBe(DEFAULT_KIND_COLORS.user)
})

test('prescribed #6 keeps cards, pills, and splines non-accent at rest and accents selected one-hop artifacts only', () => {
  const row = relationship('calls', 'Calls catalog')
  const edge = graphEdge([row])
  const nodeData = {
    boundary: false,
    childCount: 0,
    connectionCount: 1,
    context: 'System',
    description: 'Hub',
    expandable: false,
    emphasis: 'normal',
    facts: [],
    kind: 'systems',
    label: 'Hub',
    members: [],
    onExpand: () => undefined,
    row: { id: 'hub', intervals: [], name: 'Hub' },
    statuses: [],
  }
  const node = (selected: boolean) => ArchitectureNodeView({ data: nodeData, selected } as never)
  const { container, rerender } = render(<>{node(false)}{edgeElement(edge, 1, 'normal', true)}</>)
  const dataChip = dataKindChip('systems')
  if (dataChip instanceof HTMLElement) container.append(dataChip)

  const card = container.querySelector<HTMLElement>('.architecture-node')!
  expect(card.style.getPropertyValue('--card-border')).toBe('var(--kind-color)')
  expect(card.style.getPropertyValue('--kind-color')).toBe('var(--kind-system)')
  expect(container.querySelector('.kind-pill')?.getAttribute('data-kind')).toBe('systems')
  expect(container.querySelector('.data-kind-chip')?.getAttribute('data-kind')).toBe('systems')
  expect(screen.getByTestId('spline').style.stroke).toBe('var(--edge)')

  rerender(<>{node(true)}{edgeElement(edge, 1, 'outgoing', true)}{edgeElement(edge, 1, 'unrelated', true, 'unrelated')}</>)
  expect(container.querySelector<HTMLElement>('.architecture-node')!.style.getPropertyValue('--card-border')).toBe('var(--accent)')
  expect(screen.getByTestId('spline').style.stroke).toBe('var(--accent)')
  expect(screen.getByTestId('unrelated').style.stroke).toBe('var(--edge)')
  expect(container.querySelectorAll('.edge-port')).toHaveLength(4)
  expect(container.querySelectorAll('.edge-port[data-accent="true"]')).toHaveLength(2)
})
