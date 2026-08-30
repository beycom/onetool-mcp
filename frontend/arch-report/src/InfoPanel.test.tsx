// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { InfoPanel, type Selection } from './InfoPanel'
import payloadFixture from './fixture-payload.json'
import { projectState } from './projection'
import type { ReportPayload, RowKind, View } from './types'

const payload = payloadFixture as unknown as ReportPayload
const view: View = {
  aspect: 'call-direction', compare: 'off', comparePosition: 0, deps: null, expand: [],
  lens: [], position: 0, scope: null, theme: 'light', timeline: 0,
}

afterEach(cleanup)

function selection(kind: RowKind, id: string): Selection {
  return { type: 'row', kind, members: [], row: payload.rows[kind].find((row) => row.id === id)! }
}

function panel(selected: Selection, onSelect = vi.fn()) {
  return render(<InfoPanel
    aspect="call-direction"
    diff={null}
    hasBack={false}
    onBack={() => undefined}
    onClose={() => undefined}
    onDependencyView={() => undefined}
    onSelect={onSelect}
    payload={payload}
    projected={projectState(payload, view)}
    selection={selected}
    timeline={0}
  />)
}

test('Info humanizes every key and Contains links to child rows', () => {
  const onSelect = vi.fn()
  const { container } = panel(selection('systems', 'legacy-commerce'), onSelect)

  expect(screen.getByText('Availability target')).toBeTruthy()
  expect([...container.querySelectorAll('dt')].every((label) => !label.textContent?.includes('_'))).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Commerce Monolith' }))
  expect(onSelect).toHaveBeenCalledWith('containers', expect.objectContaining({ id: 'commerce-monolith' }))
})

test('interface Info resolves endpoints, direction, and lifecycle without a Connections tab', () => {
  panel(selection('interfaces', 'agent-to-monolith'))

  expect(screen.getByRole('button', { name: 'Customer Service Agent' })).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Commerce Monolith' })).toBeTruthy()
  expect(screen.getByText('Customer Service Agent → Commerce Monolith')).toBeTruthy()
  expect(screen.getByText('Base → 4 · Transaction Core')).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Connections' })).toBeNull()
})

test('Connections groups interfaces involving members of an expanded fixture entity', () => {
  const expanded = projectState(payload, { ...view, expand: ['systems:payment-provider'], position: 4 })
  render(<InfoPanel
    aspect="call-direction"
    diff={null}
    hasBack={false}
    onBack={() => undefined}
    onClose={() => undefined}
    onDependencyView={() => undefined}
    onSelect={() => undefined}
    payload={payload}
    projected={expanded}
    selection={selection('systems', 'payment-provider')}
    timeline={0}
  />)

  fireEvent.click(screen.getByRole('button', { name: 'Connections' }))

  expect(screen.getByRole('button', { name: /Execute tokenized payment operation/ })).toBeTruthy()
  expect(screen.getByText('No outgoing connections at this stage.')).toBeTruthy()
})
