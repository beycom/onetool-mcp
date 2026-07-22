import { readdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const packageRoot = resolve(root, 'node_modules', '@likec4', 'icons')
const packageJson = JSON.parse(
  await readFile(resolve(packageRoot, 'package.json'), 'utf8'),
)
const namespaces = {}

for (const namespace of ['aws', 'azure', 'bootstrap', 'gcp', 'tech']) {
  const files = await readdir(resolve(packageRoot, namespace))
  namespaces[namespace] = files
    .filter((file) => file.endsWith('.js') && file !== 'index.js')
    .map((file) => file.slice(0, -3))
    .sort()
}

const inventory = {
  package: { name: packageJson.name, version: packageJson.version },
  namespaces,
}

await writeFile(
  resolve(root, 'compat', 'fixtures', 'icon-inventory.json'),
  `${JSON.stringify(inventory, null, 2)}\n`,
)

console.log(
  `Generated ${Object.values(namespaces).reduce((sum, icons) => sum + icons.length, 0)} pinned icon names`,
)
