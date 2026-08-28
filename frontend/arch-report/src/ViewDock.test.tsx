// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'

import payloadFixture from './fixture-payload.json'
import type { ReportPayload, View } from './types'
import { ViewDock } from './ViewDock'

const payload = payloadFixture as unknown as ReportPayload
const view: View = {
  timeline: 0,
  position: 0,
  level: 'systems',
  scope: null,
  compare: 'off',
  comparePosition: 0,
  aspect: 'call-direction',
  deps: null,
  drill: null,
  lens: [],
  theme: 'light',
}

afterEach(cleanup)

test('Subsystem detail is hidden for empty datasets and shown when populated', () => {
  const props = {
    canvasActive: true,
    copyStatus: '',
    drillPath: [],
    legend: [],
    onCanvas: () => undefined,
    onCopy: () => undefined,
    onUp: () => undefined,
    onView: () => undefined,
    view,
  }
  const empty = { ...payload, rows: { ...payload.rows, subsystems: [] } }
  const populated = {
    ...payload,
    rows: {
      ...payload.rows,
      subsystems: [{ id: 'ss-0001', name: 'Commerce', parent: 's-0001', intervals: [] }],
    },
  }
  const { rerender } = render(<ViewDock {...props} payload={empty} />)

  expect(screen.getByLabelText('Detail').textContent).not.toContain('Subsystem')

  rerender(<ViewDock {...props} payload={populated} />)
  expect(screen.getByLabelText('Detail').textContent).toContain('Subsystem')
})
