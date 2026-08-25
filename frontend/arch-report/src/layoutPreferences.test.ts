// @vitest-environment jsdom
// @vitest-environment-options { "url": "https://onetool.local/" }

import { beforeEach, expect, test } from 'vitest'

import { defaultLayout, LAYOUT_KEY, loadLayout, saveLayout } from './layoutPreferences'

const values = new Map<string, string>()
const storage: Storage = {
  clear: () => values.clear(),
  getItem: (key) => values.get(key) ?? null,
  key: (index) => [...values.keys()][index] ?? null,
  get length() { return values.size },
  removeItem: (key) => { values.delete(key) },
  setItem: (key, value) => { values.set(key, value) },
}
Object.defineProperty(window, 'localStorage', { configurable: true, value: storage })

beforeEach(() => window.localStorage.clear())

test('panel and table layout persistence survives a save and reload', () => {
  const layout = defaultLayout()
  layout.panels.side = { collapsed: true, size: 444 }
  layout.tableLayouts.entities = [{ colId: 'id', hide: true, width: 190 }]
  expect(saveLayout(window.localStorage, layout)).toBe(true)
  expect(loadLayout(window.localStorage, { entities: new Set(['id']) })).toEqual(layout)
})

test('a table layout with an unknown column is rejected and defaults apply', () => {
  const layout = defaultLayout()
  layout.tableLayouts.entities = [{ colId: 'removed_column' }]
  window.localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout))
  expect(loadLayout(window.localStorage, { entities: new Set(['id']) })).toEqual(defaultLayout())
  expect(window.localStorage.getItem(LAYOUT_KEY)).toBeNull()
})
