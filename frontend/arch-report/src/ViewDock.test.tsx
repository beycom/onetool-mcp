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
  expand: [],
  scope: null,
  compare: 'off',
  comparePosition: 0,
  aspect: 'call-direction',
  deps: null,
  lens: [],
  theme: 'light',
  layout: null,
}

afterEach(cleanup)

test.each([undefined, { user_choice: false }])('Layout is hidden when user_choice is absent or false', (layout) => {
  render(<ViewDock {...{
    canvasActive: true,
    copyStatus: '',
    layoutMethod: 'layered' as const,
    legend: [],
    onCanvas: () => undefined,
    onCopy: () => undefined,
    onLayout: () => undefined,
    onView: () => undefined,
    payload: { ...payload, layout },
    view,
  }} />)

  expect(screen.queryByLabelText('Layout')).toBeNull()
})
