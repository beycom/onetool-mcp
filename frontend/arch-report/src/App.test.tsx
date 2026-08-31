// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createElement, useEffect, useRef, type ComponentType, type ReactNode } from 'react'
import { afterEach, expect, test, vi } from 'vitest'

const flowMock = vi.hoisted(() => ({
  nodes: [] as Array<{ data: Record<string, unknown>; id: string; selected?: boolean; type: string }>,
  api: {
    fitView: vi.fn(async () => true),
    getNodes: vi.fn(() => flowMock.nodes),
    getNodesBounds: vi.fn(() => ({ height: 200, width: 300, x: 0, y: 0 })),
    getViewport: vi.fn(() => ({ x: 0, y: 0, zoom: 1 })),
    setViewport: vi.fn(async () => true),
    zoomIn: vi.fn(async () => true),
    zoomOut: vi.fn(async () => true),
  },
}))

vi.mock('@xyflow/react', () => ({
  Background: () => null,
  BackgroundVariant: { Lines: 'lines' },
  BaseEdge: () => null,
  EdgeLabelRenderer: ({ children }: { children: ReactNode }) => children,
  Handle: () => null,
  MiniMap: (props: {
    ariaLabel: string
    className: string
    maskStrokeColor: string
    maskStrokeWidth: number
    nodeClassName: (node: { data: Record<string, unknown>; type: string }) => string
    nodeColor: (node: { data: Record<string, unknown>; type: string }) => string
  }) => {
    const user = { data: { kind: 'users' }, type: 'architecture' }
    const boundary = { data: { boundary: { kind: 'systems' } }, type: 'boundary' }
    return <div aria-label={props.ariaLabel} className={props.className} data-mask-stroke={props.maskStrokeColor} data-mask-width={props.maskStrokeWidth} role="img">
      <span className={props.nodeClassName(user)} data-color={props.nodeColor(user)} />
      <span className={props.nodeClassName(boundary)} data-color={props.nodeColor(boundary)} />
    </div>
  },
  Position: { Bottom: 'bottom', Left: 'left', Right: 'right', Top: 'top' },
  ReactFlow: ({ children, nodeTypes, nodes, onInit, onNodeClick }: {
    children?: ReactNode
    nodeTypes: Record<string, ComponentType<Record<string, unknown>>>
    nodes: Array<{ data: Record<string, unknown>; id: string; selected?: boolean; type: string }>
    onInit?: (flow: typeof flowMock.api) => void
    onNodeClick: (event: unknown, node: unknown) => void
  }) => {
    flowMock.nodes = nodes
    const initialized = useRef(false)
    useEffect(() => {
      if (initialized.current) return
      initialized.current = true
      onInit?.(flowMock.api)
    }, [onInit])
    return <div aria-label="Architecture canvas">{nodes.map((node) => <div key={node.id}>
        <button aria-label={`Select ${String(node.data.label ?? node.id)}`} onClick={() => onNodeClick({}, node)} type="button">Select</button>
        {createElement(nodeTypes[node.type], { data: node.data, id: node.id, selected: node.selected ?? false })}
      </div>)}{children}</div>
  },
  getBezierPath: () => ['', 0, 0],
}))

vi.mock('./layout', () => ({
  DEFAULT_LAYOUT_SETTINGS: { method: 'layered', direction: 'right', spacing: { node: 40, layer: 72, boundary: 20 }, ranking: 'auto' },
  NODE_HEIGHT: 112,
  NODE_WIDTH: 240,
  applyPositions: (nodes: unknown[]) => nodes,
  defaultLayoutMethod: () => 'layered',
  registeredLayoutMethods: ['layered', 'radial', 'grid'],
  makeLayoutKey: ({ timeline, expand }: { timeline: number; expand: string[] }) => `${timeline}:${expand.join(',')}`,
  stableExpansionLayout: (_previous: unknown, fresh: unknown) => fresh,
  starHub: () => null,
  unionLayout: async () => new Map([['ready', { height: 100, width: 100, x: 0, y: 0 }]]),
}))

vi.mock('./cardSize', () => ({
  cardSize: () => ({ width: 240, height: 112, nameLines: 1 }),
  measureCardText: () => 10,
}))

import App from './App'
import payload from './fixture-payload.json'
import type { ReportPayload } from './types'
import { presetExpansion } from './view'

afterEach(() => {
  cleanup()
  history.replaceState(null, '', '#')
  vi.clearAllMocks()
  vi.restoreAllMocks()
})

test('the Stage dropdown has every position and changes the projected state', async () => {
  render(<App />)
  const nodeIds = screen.getByTestId('rendered-node-ids')
  const initial = nodeIds.textContent
  const stage = screen.getByLabelText('Stage') as HTMLSelectElement

  expect(stage.options).toHaveLength(payload.timelines[0].milestones.length + 1)
  fireEvent.change(stage, { target: { value: '1' } })

  await waitFor(() => expect(nodeIds.textContent).not.toBe(initial))
  expect(nodeIds.textContent).toContain('systems:commerce-platform')
})

test('stage changes move changed fields into Info and remove the card popover', async () => {
  history.replaceState(null, '', '#level=containers')
  const { container } = render(<App />)
  fireEvent.change(screen.getByLabelText('Stage'), { target: { value: '1' } })

  const select = await screen.findByLabelText('Select Commerce Monolith')
  fireEvent.click(select)

  expect(await screen.findByText('Changes at this stage')).toBeTruthy()
  expect(screen.getByText('Changed')).toBeTruthy()
  expect(screen.getAllByText('→').length).toBeGreaterThan(0)
  expect(container.querySelector('.change-popover')).toBeNull()
})

test('Escape closes search before clearing the selection and Info', async () => {
  render(<App />)
  fireEvent.click(await screen.findByLabelText('Select Legacy Commerce Platform'))
  expect(screen.getByLabelText('Close details')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: /Search/ }))

  fireEvent.keyDown(window, { key: 'Escape' })
  await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Global search' })).toBeNull())
  expect(screen.getByLabelText('Close details')).toBeTruthy()

  fireEvent.keyDown(window, { key: 'Escape' })
  await waitFor(() => expect(screen.queryByLabelText('Close details')).toBeNull())
})

test('View has no Detail control and a legacy level link restores its expansion in one history entry', async () => {
  history.replaceState(null, '', '#level=containers')
  const push = vi.spyOn(history, 'pushState')
  render(<App />)

  expect(screen.queryByLabelText('Detail')).toBeNull()
  await waitFor(() => expect(new URLSearchParams(location.hash.slice(1)).get('expand')).not.toBeNull())
  expect(new URLSearchParams(location.hash.slice(1)).get('expand')?.split(',')).toEqual(presetExpansion(payload as unknown as ReportPayload, 'containers'))
  expect(push).toHaveBeenCalledTimes(1)
})

test('Reset view clears expansion, refits once, and Back restores the expansion', async () => {
  history.replaceState(null, '', '#expand=systems%3Alegacy-commerce')
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(800)
  vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(600)
  const push = vi.spyOn(history, 'pushState')
  render(<App />)
  const reset = await screen.findByRole('button', { name: 'Reset view' })
  const expandedHash = location.hash
  await waitFor(() => expect(flowMock.api.setViewport).toHaveBeenCalled())
  flowMock.api.setViewport.mockClear()

  fireEvent.click(reset)

  await waitFor(() => expect(screen.queryByRole('button', { name: 'Reset view' })).toBeNull())
  expect(new URLSearchParams(location.hash.slice(1)).get('expand')).toBeNull()
  expect(push).toHaveBeenCalledTimes(1)
  await waitFor(() => expect(flowMock.api.setViewport).toHaveBeenCalledTimes(1))

  history.replaceState(null, '', expandedHash)
  window.dispatchEvent(new PopStateEvent('popstate'))
  expect(await screen.findByRole('button', { name: 'Reset view' })).toBeTruthy()
})

test('tag lens reports matches and marks exactly the matching cards', async () => {
  const { container } = render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: /Show all/ }))
  fireEvent.click(screen.getByRole('button', { name: /ecommerce/i }))

  const matched = container.querySelectorAll(".architecture-node[data-tag-match='true']")
  expect(matched.length).toBeGreaterThan(0)
  expect(await screen.findByText(`1 tag · ${matched.length} ${matched.length === 1 ? 'entity' : 'entities'} matched`)).toBeTruthy()
})

test('dependency fallback hides canvas controls and styles Return to map', async () => {
  history.replaceState(null, '', '#deps=containers%3Acommerce-monolith')
  const { container } = render(<App />)

  expect(await screen.findByText('The focused entity is not in this projection.')).toBeTruthy()
  expect(screen.queryByRole('group', { name: 'Map, fit, and zoom' })).toBeNull()
  expect(screen.getByRole('button', { name: 'Return to map' }).classList.contains('secondary-action')).toBe(true)
  expect(container.querySelector('.layout-indicator')).toBeNull()
})

test('minimap renders an accent viewport and kind-coloured nodes without a floating label', async () => {
  const { container } = render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: 'Toggle map' }))

  const minimap = screen.getByRole('img', { name: 'Architecture minimap' })
  expect(minimap.getAttribute('data-mask-stroke')).toBe('var(--accent)')
  expect(minimap.getAttribute('data-mask-width')).toBe('3')
  expect(minimap.querySelector('.minimap-node-architecture')?.getAttribute('data-color')).toBe('var(--kind-user)')
  expect(minimap.querySelector('.minimap-node-boundary')?.getAttribute('data-color')).toBe('var(--kind-system)')
  expect(container.querySelector('.map-label')).toBeNull()
})
