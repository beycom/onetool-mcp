import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, test } from 'vitest'

import type { TableConfig } from '../src/data/types'
import { parseFragment, serializeFragment } from '../src/explorer/fragment'
import { sanitizeSystemSet } from '../src/explorer/ExplorerProvider'
import {
  DEFAULT_PREFERENCES,
  loadPreferences,
  PREFERENCES_KEY,
  savePreferences,
} from '../src/explorer/preferences'
import {
  appendBoundedHistory,
  initialDiagramId,
  MAX_SOLUTION_HISTORY,
  withDiagram,
} from '../src/explorer/state'
import {
  selectedRowsAsTsv,
  validateGridConfig,
} from '../src/grid/ArchitectureGrid'

const root = fileURLToPath(new URL('../', import.meta.url))
const source = (path: string) => readFileSync(`${root}${path}`, 'utf8')

describe('offline explorer components', () => {
  test('grid-current-view-export', () => {
    expect(
      selectedRowsAsTsv(
        [{ id: 'sys-a', name: 'A\tname', kind: 'system', status: 'Added' }],
        ['id', 'name'],
      ),
    ).toBe('id\tname\nsys-a\tA name')
  })

  test('grid-schema-layout-fallback', () => {
    const config: TableConfig = {
      id: 'architecture',
      schema_version: 1,
      density: 'comfortable',
      columns: [{ id: 'name', pinned: 'left', visible: true, width: 240 }],
    }
    const result = validateGridConfig(config, new Set(['id', 'name']), undefined)
    expect(result).toMatchObject({ valid: true })
    expect(result.columns).toEqual([
      { colId: 'name', hide: false, pinned: 'left', width: 240 },
    ])
  })

  test('grid-invalid-config', () => {
    const config: TableConfig = {
      id: 'architecture',
      schema_version: 1,
      density: 'compact',
      columns: [{ id: 'retired-column' }],
    }
    expect(validateGridConfig(config, new Set(['id']), undefined)).toMatchObject({
      valid: false,
      diagnostic: "Stored table layout references unknown column 'retired-column'",
    })
  })

  test('grid-community-only', () => {
    const modules = source('src/grid/modules.ts')
    const manifest = source('package.json')
    expect(modules).toContain("from 'ag-grid-community'")
    expect(modules).not.toMatch(/Enterprise|ag-grid-enterprise/)
    expect(manifest).not.toContain('ag-grid-enterprise')
  })

  test('grid-copy-selected-rows', () => {
    expect(
      selectedRowsAsTsv(
        [
          { id: 'i-a-d', name: 'A to D', kind: 'interface', status: 'Changed' },
          { id: 'sys-d', name: 'System D\nnext', kind: 'system', status: 'Added' },
        ],
        ['id', 'status'],
      ),
    ).toBe('id\tstatus\ni-a-d\tChanged\nsys-d\tAdded')
  })

  test('diagram-state-preserves-solution-context-and-prefers-fragments', () => {
    const current = { graphId: 'preferred:2', diagramId: 'saved', snapshotOrder: 2 }
    expect(withDiagram(current, 'overview')).toEqual({
      graphId: 'preferred:2',
      diagramId: 'overview',
      snapshotOrder: 2,
    })
    expect(initialDiagramId(undefined, 'saved')).toBe('saved')
    expect(initialDiagramId('fragment', 'saved')).toBe('fragment')
  })

  test('solution-history-is-bounded-and-discards-forward-entries', () => {
    let history = Array.from({ length: MAX_SOLUTION_HISTORY }, (_, value) => ({ value }))
    let index = history.length - 1
    ;({ history, index } = appendBoundedHistory(history, index, { value: 100 }))
    expect(history).toHaveLength(MAX_SOLUTION_HISTORY)
    expect(history[0]).toEqual({ value: 1 })
    expect(index).toBe(MAX_SOLUTION_HISTORY - 1)

    ;({ history, index } = appendBoundedHistory(history, 10, { value: 999 }))
    expect(history.slice(-2)).toEqual([{ value: 11 }, { value: 999 }])
    expect(index).toBe(11)
  })

  test('shared-controls-states', () => {
    const screens = source('src/explorer/ExplorerScreens.tsx')
    for (const label of ['Systems', 'System groups', 'Changes', 'Change groups', 'Tags']) {
      expect(screens).toContain(`label: '${label}'`)
    }
    expect(screens).toContain('aria-pressed')
  })

  test('keyboard-and-focus', () => {
    const css = source('src/styles.css')
    expect(css).toContain(':focus-visible')
    expect(source('src/App.tsx')).toContain('Skip to architecture canvas')
    expect(source('src/explorer/ExplorerShell.tsx')).toContain("'Architecture browsing'")
  })

  test('fragment-link-restore', () => {
    const fragment = serializeFragment({
      graph: 'preferred:2',
      browse: 'system_group',
      order: 2,
      depth: 1,
      level: 'application',
      colorBy: 'tag',
      search: 'A & D',
      diagram: 'system_context',
      selected: 'arch-v2-interface-a-to-d',
      dataOpen: true,
      inspectorOpen: true,
      activeTable: 'included_interfaces',
      statuses: ['new', 'change'],
    })
    expect(parseFragment(fragment)).toEqual({
      graph: 'preferred:2',
      browse: 'system_group',
      order: 2,
      depth: 1,
      level: 'application',
      colorBy: 'tag',
      search: 'A & D',
      diagram: 'system_context',
      selected: 'arch-v2-interface-a-to-d',
      dataOpen: true,
      inspectorOpen: true,
      activeTable: 'included_interfaces',
      statuses: ['new', 'change'],
    })
  })

  test('obsolete-fragment-selectors-fall-back-to-known-values', () => {
    expect(
      sanitizeSystemSet(
        {
          systems: ['A', 'retired-system'],
          system_groups: ['retired-group'],
          changes: ['delivery'],
          change_groups: [],
          tags: ['core', 'retired-tag'],
        },
        {
          systems: ['A', 'B'],
          system_groups: { platform: ['A'] },
          changes: { delivery: ['A'] },
          change_groups: { wave: ['A'] },
          change_impacts: {},
          change_group_impacts: {},
          tags: { core: ['A'] },
        },
      ),
    ).toEqual({
      systems: ['A'],
      system_groups: [],
      changes: ['delivery'],
      change_groups: [],
      tags: ['core'],
    })
  })

  test('preferences-are-versioned-and-invalid-values-reset', () => {
    const values = new Map<string, string>()
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      removeItem: (key: string) => values.delete(key),
      setItem: (key: string, value: string) => values.set(key, value),
    }
    expect(savePreferences(storage, DEFAULT_PREFERENCES)).toBe(true)
    expect(loadPreferences(storage)).toEqual(DEFAULT_PREFERENCES)
    values.set(PREFERENCES_KEY, JSON.stringify({ schemaVersion: 0 }))
    expect(loadPreferences(storage)).toEqual(DEFAULT_PREFERENCES)
    expect(values.has(PREFERENCES_KEY)).toBe(false)
  })
})
