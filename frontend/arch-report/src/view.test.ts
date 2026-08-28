// @vitest-environment jsdom

import { expect, test } from 'vitest'

import payloadFixture from '../../../tests/unit/tools/fixtures/arch/projection/payload.json'
import type { ReportPayload } from './types'
import { decodeView, encodeView } from './view'

const payload = payloadFixture as unknown as ReportPayload

test('select fragment round-trips and ignores an invalid id', () => {
  const entityKey = `systems:${payload.rows.systems[0].id}`
  const interfaceKey = `interfaces:${payload.rows.interfaces[0].id}`
  const entityResult = decodeView(payload, `#select=${entityKey}`)
  const interfaceResult = decodeView(payload, `#${encodeView(entityResult.view, interfaceKey)}`)

  expect(entityResult.select).toBe(entityKey)
  expect(interfaceResult.select).toBe(interfaceKey)

  const invalidResult = decodeView(payload, '#select=systems:missing')
  expect(invalidResult.select).toBeNull()
  expect(invalidResult.diagnostics).toContain('view.fragment.select.systems:missing: unknown row id ignored')
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
