// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('@xyflow/react', () => ({
  Background: () => null,
  BackgroundVariant: { Lines: 'lines' },
  BaseEdge: () => null,
  EdgeLabelRenderer: ({ children }: { children: ReactNode }) => children,
  Handle: () => null,
  MarkerType: { ArrowClosed: 'arrowclosed' },
  MiniMap: () => null,
  Position: { Left: 'left', Right: 'right' },
  ReactFlow: ({ nodes }: { nodes: Array<{ id: string }> }) => (
    <div aria-label="Architecture canvas">{nodes.map((node) => <span key={node.id}>{node.id}</span>)}</div>
  ),
  getSmoothStepPath: () => ['', 0, 0],
}))

vi.mock('./layout', () => ({
  NODE_HEIGHT: 112,
  NODE_WIDTH: 240,
  applyPositions: (nodes: unknown[]) => nodes,
  unionLayout: async () => new Map(),
}))

import App from './App'

afterEach(cleanup)

test('scrubbing the acme timeline changes the rendered node set', async () => {
  render(<App />)
  const nodeIds = screen.getByTestId('rendered-node-ids')
  const current = nodeIds.textContent

  fireEvent.change(screen.getByLabelText('Architecture position'), { target: { value: '1' } })

  await waitFor(() => expect(nodeIds.textContent).not.toBe(current))
  expect(nodeIds.textContent).toContain('systems:commerce-platform')
})
