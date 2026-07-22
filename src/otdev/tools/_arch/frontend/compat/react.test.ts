import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, test } from 'vitest'

const ROOT = resolve(import.meta.dirname, '..')

describe('LikeC4 React integration compatibility', () => {
  test('likec4-react-hooks-compat', async () => {
    const reactApi = await import('likec4/react')

    expect(reactApi.useCurrentViewId).toBeTypeOf('function')
    expect(reactApi.useDiagram).toBeTypeOf('function')
    expect(reactApi.ReactLikeC4).toBeTypeOf('function')
  })

  test('one Mantine provider and required CSS order', () => {
    const app = readFileSync(resolve(ROOT, 'src', 'App.tsx'), 'utf8')
    const css = readFileSync(resolve(ROOT, 'src', 'styles.css'), 'utf8')

    expect(app.match(/<MantineProvider\b/g)).toHaveLength(1)
    expect(css.indexOf('@mantine/core/styles.layer.css')).toBeLessThan(
      css.indexOf('@likec4/diagram/styles-min.css'),
    )
    expect(css.indexOf('@likec4/diagram/styles-min.css')).toBeLessThan(
      css.indexOf(':root'),
    )
  })
})
