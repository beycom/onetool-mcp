// @vitest-environment jsdom

import { expect, test } from 'vitest'

import payloadFixture from '../../../tests/unit/tools/fixtures/arch/projection/payload.json'
import type { ReportPayload } from './types'
import { decodeView, encodeView } from './view'

const payload = payloadFixture as unknown as ReportPayload

test('expand round-trips, drops invalid ids, and maps a legacy drill to expansion plus selection', () => {
  const decoded = decodeView(payload, '#expand=systems:sysA,systems:missing,users:u1')
  const roundTrip = decodeView(payload, `#${encodeView(decoded.view)}`)

  expect(decoded.view.expand).toEqual(['systems:sysA'])
  expect(roundTrip.view.expand).toEqual(decoded.view.expand)
  expect(decoded.diagnostics).toEqual([
    'view.fragment.expand.systems:missing: unknown or childless entity id ignored',
    'view.fragment.expand.users:u1: unknown or childless entity id ignored',
  ])

  const legacy = decodeView(payload, '#drill=subsystems:ssA')
  expect(legacy.view.expand).toEqual(['subsystems:ssA', 'systems:sysA'])
  expect(legacy.select).toBe('subsystems:ssA')
})

test('removed fragment keys are ignored with a diagnostic', () => {
  const result = decodeView(payload, '#scope=system-a&hops=3&compare=base&compare-at=2&theme=dark')
  const fragment = encodeView(result.view, result.select)

  expect(result.view).toMatchObject({ compare: 'off', comparePosition: 0, scope: null, theme: 'light' })
  expect(fragment).not.toMatch(/(?:scope|hops|compare|compare-at|theme)=/)
  for (const key of ['scope', 'hops', 'compare', 'compare-at', 'theme']) {
    expect(result.diagnostics).toContain(`view.fragment.${key}: ignored retired or local-only key`)
  }
})
