import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, test } from 'vitest'

const FIXTURES = resolve(import.meta.dirname, 'fixtures')

describe('generated identifier and icon inventories', () => {
  test('generated-id-mapping is unique and stable', () => {
    const fixture = JSON.parse(
      readFileSync(resolve(FIXTURES, 'generated-identifiers.json'), 'utf8'),
    ) as { canonicalToLikeC4: Record<string, string> }
    const generated = Object.values(fixture.canonicalToLikeC4)

    expect(new Set(generated).size).toBe(generated.length)
    expect(generated).toContain('platform.api.ledger')
    expect(generated).toContain('payment_flow')
  })

  test('pinned icon inventory covers every approved namespace', () => {
    const fixture = JSON.parse(
      readFileSync(resolve(FIXTURES, 'icon-inventory.json'), 'utf8'),
    ) as {
      package: { name: string; version: string }
      namespaces: Record<string, string[]>
    }

    expect(fixture.package).toEqual({ name: '@likec4/icons', version: '1.46.4' })
    expect(Object.keys(fixture.namespaces).sort()).toEqual([
      'aws',
      'azure',
      'bootstrap',
      'gcp',
      'tech',
    ])
    for (const icons of Object.values(fixture.namespaces)) {
      expect(icons.length).toBeGreaterThan(10)
      expect(icons).toEqual([...icons].sort())
    }
  })
})
