// @vitest-environment jsdom

import { expect, test } from 'vitest'

import payloadFixture from '../../../tests/unit/tools/fixtures/arch/projection/payload.json'
import type { ReportPayload } from './types'
import { decodeView, encodeView } from './view'

const payload = payloadFixture as unknown as ReportPayload

test('view fragments omit retired mode and local layout coordinates', () => {
  const view = decodeView(payload, '#mode=PATH&x=12&width=480').view
  const fragment = encodeView(view)
  expect(fragment).not.toMatch(/(?:mode|x|y|zoom|width|height|size)=/)
})

test('unknown fragment ids follow the diagnostic path without crashing', () => {
  const result = decodeView(payload, '#scope=missing-system')
  expect(result.view.scope?.systems).toEqual([])
  expect(result.diagnostics).toContain('view.fragment.scope.missing-system: unknown system id ignored')
})
