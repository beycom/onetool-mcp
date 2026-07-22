import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const lock = JSON.parse(readFileSync(resolve(root, 'package-lock.json'), 'utf8'))
const rootPackage = lock.packages['']
const exactVersion = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/

for (const [name, version] of Object.entries({
  ...rootPackage.dependencies,
  ...rootPackage.devDependencies,
})) {
  if (!exactVersion.test(version)) {
    throw new Error(`${name} must use an exact version, received ${version}`)
  }
}

const packageNames = Object.keys(lock.packages)
  .filter((path) => path.includes('node_modules/'))
  .map((path) => path.slice(path.lastIndexOf('node_modules/') + 'node_modules/'.length))

const enterprise = packageNames.filter(
  (name) => name === 'ag-grid-enterprise' || name.startsWith('@ag-grid-enterprise/'),
)
if (enterprise.length > 0) {
  throw new Error(`AG Grid Enterprise packages are forbidden: ${enterprise.join(', ')}`)
}

const tree = JSON.parse(
  execFileSync('npm', ['ls', '--all', '--json'], { cwd: root, encoding: 'utf8' }),
)

function collectVersions(node, packageName, versions = new Set()) {
  for (const [name, dependency] of Object.entries(node.dependencies ?? {})) {
    if (name === packageName && dependency.version) {
      versions.add(dependency.version)
    }
    collectVersions(dependency, packageName, versions)
  }
  return versions
}

for (const [name, expected] of Object.entries({
  react: '19.2.7',
  'react-dom': '19.2.7',
  '@mantine/core': '9.2.2',
  '@mantine/hooks': '9.2.2',
})) {
  const versions = [...collectVersions(tree, name)]
  if (versions.length !== 1 || versions[0] !== expected) {
    throw new Error(`${name} must resolve once to ${expected}; received ${versions.join(', ')}`)
  }
}

const missingLicenses = []
for (const [packagePath, packageMetadata] of Object.entries(lock.packages)) {
  if (!packagePath.includes('node_modules/')) continue
  const installedPath = resolve(root, packagePath)
  const hasLicenceFile = ['LICENSE', 'LICENSE.md', 'LICENSE.txt', 'LICENCE'].some((name) =>
    existsSync(resolve(installedPath, name)),
  )
  if (!packageMetadata.license && !hasLicenceFile) {
    missingLicenses.push(`${packagePath}@${packageMetadata.version}`)
  }
}
if (missingLicenses.length > 0) {
  throw new Error(`Dependencies without declared licences: ${missingLicenses.join(', ')}`)
}

console.log(
  `Verified ${packageNames.length} locked packages, one React/Mantine tree, package licences, and no AG Grid Enterprise code`,
)
