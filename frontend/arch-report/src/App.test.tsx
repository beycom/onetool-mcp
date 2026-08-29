// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createElement, type ComponentType, type ReactNode } from 'react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('@xyflow/react', () => ({
  Background: () => null,
  BackgroundVariant: { Lines: 'lines' },
  BaseEdge: () => null,
  EdgeLabelRenderer: ({ children }: { children: ReactNode }) => children,
  Handle: () => null,
  MiniMap: () => null,
  Position: { Bottom: 'bottom', Left: 'left', Right: 'right', Top: 'top' },
  ReactFlow: ({ nodeTypes, nodes, onNodeClick }: {
    nodeTypes: Record<string, ComponentType<Record<string, unknown>>>
    nodes: Array<{ data: Record<string, unknown>; id: string; selected?: boolean; type: string }>
    onNodeClick: (event: unknown, node: unknown) => void
  }) => (
    <div aria-label="Architecture canvas">{nodes.map((node) => <div key={node.id}>
      <button aria-label={`Select ${String(node.data.label ?? node.id)}`} onClick={() => onNodeClick({}, node)} type="button">Select</button>
      {createElement(nodeTypes[node.type], { data: node.data, id: node.id, selected: node.selected ?? false })}
    </div>)}</div>
  ),
  getBezierPath: () => ['', 0, 0],
}))

vi.mock('./layout', () => ({
  NODE_HEIGHT: 112,
  NODE_WIDTH: 240,
  applyPositions: (nodes: unknown[]) => nodes,
  makeLayoutKey: ({ timeline, expand }: { timeline: number; expand: string[] }) => `${timeline}:${expand.join(',')}`,
  stableExpansionLayout: (_previous: unknown, fresh: unknown) => fresh,
  starHub: () => null,
  unionLayout: async () => new Map(),
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
  const { container } = render(<App />)
  fireEvent.change(screen.getByLabelText('Detail'), { target: { value: 'containers' } })
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

test('Detail presets write one history entry and hand expansion displays Custom', async () => {
  const push = vi.spyOn(history, 'pushState')
  render(<App />)

  fireEvent.change(screen.getByLabelText('Detail'), { target: { value: 'containers' } })
  await waitFor(() => expect((screen.getByLabelText('Detail') as HTMLSelectElement).value).toBe('containers'))
  expect(new URLSearchParams(location.hash.slice(1)).get('expand')?.split(',')).toEqual(presetExpansion(payload as unknown as ReportPayload, 'containers'))
  expect(push).toHaveBeenCalledTimes(1)

  fireEvent.click(screen.getAllByRole('button', { name: /^Expand / })[0])
  await waitFor(() => expect((screen.getByLabelText('Detail') as HTMLSelectElement).value).toBe('custom'))
})
