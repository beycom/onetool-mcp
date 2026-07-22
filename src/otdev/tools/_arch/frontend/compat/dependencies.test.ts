import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, test } from 'vitest'

const ROOT = resolve(import.meta.dirname, '..')

function installedVersion(packageName: string): string {
  const packageJson = JSON.parse(
    readFileSync(resolve(ROOT, 'node_modules', packageName, 'package.json'), 'utf8'),
  ) as { version: string }
  return packageJson.version
}

describe('pinned frontend dependency set', () => {
  test.each([
    ['likec4', '1.58.0'],
    ['@likec4/core', '1.58.0'],
    ['@likec4/diagram', '1.58.0'],
    ['@likec4/layouts', '1.58.0'],
    ['@likec4/generators', '1.58.0'],
    ['@likec4/icons', '1.46.4'],
    ['react', '19.2.7'],
    ['react-dom', '19.2.7'],
    ['@mantine/core', '9.2.2'],
    ['@mantine/hooks', '9.2.2'],
    ['ag-grid-community', '36.0.1'],
    ['ag-grid-react', '36.0.1'],
  ])('%s is pinned to %s', (packageName, expected) => {
    expect(installedVersion(packageName)).toBe(expected)
  })
})
