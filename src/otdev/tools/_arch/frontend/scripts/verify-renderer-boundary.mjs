import { readdirSync, readFileSync } from 'node:fs'
import { relative, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const ignored = new Set(['dist', 'node_modules'])
const extensions = new Set(['.css', '.d.ts', '.mjs', '.ts', '.tsx'])
const importPattern = /(?:from\s+|import\s*\(|@import\s+|reference\s+types=)["']?(?:@likec4|likec4(?=[:/'"]))/
const lowLevelPattern = /\b(?:ComputedView|DiagramView|modelRef|_stage|_type)\b|as never|as unknown as/
const importAllowlist = new Set([
  'compat/likec4.test.ts',
  'compat/react.test.ts',
  'scripts/compile-likec4.mjs',
  'scripts/export-likec4.mjs',
  'src/styles.css',
  'src/vite-env.d.ts',
  'vite.config.ts',
])
const lowLevelAllowlist = new Set(['compat/likec4.test.ts'])

function files(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (ignored.has(entry.name)) return []
    const path = resolve(directory, entry.name)
    return entry.isDirectory() ? files(path) : [path]
  })
}

function extension(path) {
  return path.endsWith('.d.ts') ? '.d.ts' : path.slice(path.lastIndexOf('.'))
}

const inventory = []
const violations = []
for (const path of files(root).filter((candidate) => extensions.has(extension(candidate)))) {
  const name = relative(root, path)
  if (name === 'scripts/verify-renderer-boundary.mjs') continue
  const content = readFileSync(path, 'utf8')
  const adapter = name.startsWith('src/solution/renderer/')
  if (importPattern.test(content)) {
    inventory.push(name)
    if (!adapter && !importAllowlist.has(name)) violations.push(`${name}: renderer import`)
  }
  if (lowLevelPattern.test(content) && !adapter && !lowLevelAllowlist.has(name)) {
    violations.push(`${name}: low-level renderer field or cast`)
  }
}

if (violations.length > 0) {
  throw new Error(`Renderer boundary violations:\n${violations.sort().join('\n')}`)
}

console.log(`Renderer boundary verified; explicit inventory: ${inventory.sort().join(', ')}`)
