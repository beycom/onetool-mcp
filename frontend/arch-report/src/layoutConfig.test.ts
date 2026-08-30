import { expect, test } from 'vitest'

import { configuredLayoutMethod, loadLayoutMethod, queryLayoutMethod, resolveLayoutMethod, saveLayoutMethod } from './layoutConfig'

test('layout restore priority is query, hash, stored, then config', () => {
  const values = new Map<string, string>()
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value) },
  }
  expect(saveLayoutMethod(storage, 'acme.yaml', 'grid')).toBe(true)
  const stored = loadLayoutMethod(storage, 'acme.yaml')
  const config = configuredLayoutMethod({ method: 'layered' })

  expect(resolveLayoutMethod({ query: queryLayoutMethod('?layout=radial', true), hash: 'layered', stored, config })).toBe('radial')
  expect(resolveLayoutMethod({ query: null, hash: 'layered', stored, config })).toBe('layered')
  expect(resolveLayoutMethod({ query: null, hash: null, stored, config })).toBe('grid')
  expect(resolveLayoutMethod({ query: null, hash: null, stored: null, config })).toBe('layered')
})
