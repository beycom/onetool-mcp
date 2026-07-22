import { generateDrawio, generateDrawioMulti, getAllDiagrams } from '@likec4/generators'
import { LikeC4 } from 'likec4'
import { beforeAll, describe, expect, test } from 'vitest'

import type { LikeC4Model } from '@likec4/core/model'

let model: LikeC4Model.Layouted

beforeAll(async () => {
  const api = await LikeC4.fromWorkspace('likec4', {
    printErrors: false,
    throwIfInvalid: true,
  })
  expect(api.getErrors()).toEqual([])
  model = await api.layoutedModel()
})

describe('pinned LikeC4 compatibility', () => {
  test('likec4-layout-compat', () => {
    const index = model.view('index')

    expect(index).toBeDefined()
    expect(index.$view.nodes.length).toBeGreaterThan(0)
    expect(index.$view.edges.length).toBeGreaterThan(0)
    expect(index.$view.bounds.width).toBeGreaterThan(0)
    expect(index.$view.bounds.height).toBeGreaterThan(0)
  })

  test('likec4-dynamic-sequence-compat', () => {
    const dynamic = model.view('payment_flow')

    expect(dynamic.isDynamicView()).toBe(true)
    if (!dynamic.isDynamicView()) {
      throw new Error('payment_flow must remain a dynamic view')
    }
    expect(dynamic.$view._type).toBe('dynamic')
    expect(dynamic.$view.variant).toBe('diagram')
    expect(dynamic.$view.sequenceLayout).toBeDefined()
    expect(dynamic.$view.sequenceLayout?.actors.length).toBeGreaterThan(1)
    expect(dynamic.$view.sequenceLayout?.steps.length).toBeGreaterThan(1)
  })

  test('likec4-drawio-compat', () => {
    const index = model.view('index')
    const dynamic = model.view('payment_flow')
    const modified = '2026-01-01T00:00:00.000Z'
    const single = generateDrawio(index, { compressed: false, modified })
    const multi = generateDrawioMulti([index, dynamic], undefined, modified)

    expect(single).toContain('<mxfile host="LikeC4"')
    expect(getAllDiagrams(single)).toHaveLength(1)
    expect(getAllDiagrams(multi).map((diagram) => diagram.name)).toEqual([
      'Payments landscape',
      'Payment flow',
    ])
  })
})
