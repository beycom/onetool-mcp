import { execFileSync } from 'node:child_process'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { chromium } from 'playwright'

const root = resolve(import.meta.dirname, '..')
const temporary = await mkdtemp(join(tmpdir(), 'onetool-arch-grid-benchmark-'))
const dataPath = resolve(temporary, 'architecture-data.json')
const output = resolve(temporary, 'dist')
const sample = JSON.parse(await readFile(resolve(root, 'src', 'data', 'sample-data.json'), 'utf8'))
const graph = sample.graphs[0]

graph.nodes = Array.from({ length: 5_000 }, (_, index) => {
  const number = index + 1
  return {
    id: `entity-${String(number).padStart(5, '0')}`,
    entity_kind: 'system',
    name: `Architecture entity ${number}`,
    children: [],
    status: number % 4 === 0 ? 'Changed' : 'No Change',
    context_status: number % 4 === 0 ? 'change' : 'no_change',
    tombstone: false,
    future: false,
    tags: [`tag-${number % 9}`],
    groups: [`group-${number % 12}`],
    related_changes: [],
    properties: { owner: `team-${number % 20}` },
  }
})
graph.edges = []
graph.containers = []
sample.title = 'Architecture grid benchmark'
sample.canonicalToLikec4ByGraph[graph.id] = {}
sample.likec4EdgeToCanonicalByGraph[graph.id] = {}

await writeFile(dataPath, `${JSON.stringify(sample)}\n`)
execFileSync(resolve(root, 'node_modules', '.bin', 'vite'), ['build', '--outDir', output], {
  cwd: root,
  env: { ...process.env, ONETOOL_ARCH_DATA: dataPath },
  stdio: 'ignore',
})
const pageHtmlBytes = (await readFile(resolve(output, 'index.html'))).byteLength

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
const networkRequests = []

await page.route(/https?:\/\//, async (route) => {
  networkRequests.push(route.request().url())
  await route.abort('blockedbyclient')
})

try {
  const started = performance.now()
  await page.goto(pathToFileURL(resolve(output, 'index.html')).href)
  await page.getByRole('button', { name: 'Show data' }).click()
  await page.getByTestId('architecture-grid').waitFor()
  await page.locator('.ag-row').first().waitFor()
  const startupMs = performance.now() - started
  const screenReaderRolesPresent =
    (await page.getByRole('grid').count()) === 1 &&
    (await page.getByRole('columnheader').count()) >= 7 &&
    (await page.getByRole('searchbox', { name: 'Search elements' }).count()) === 1

  await page.getByRole('button', { name: 'Columns' }).click()
  await page.getByRole('menu').waitFor()
  const shellOverlayRendered = true
  await page.keyboard.press('Escape')

  const search = page.getByRole('searchbox', { name: 'Search elements' })
  const filterStarted = performance.now()
  await search.fill('entity-04999')
  await page.getByText('Architecture entity 4999', { exact: true }).waitFor()
  const filterMs = performance.now() - filterStarted

  await search.fill('')
  const stableIdHeader = page.getByRole('columnheader', { name: /Stable ID/ })
  await stableIdHeader.click()
  const sortStarted = performance.now()
  await stableIdHeader.click()
  await page
    .locator('[role="gridcell"][col-id="id"]')
    .first()
    .getByText('entity-05000', { exact: true })
    .waitFor()
  const sortMs = performance.now() - sortStarted

  await search.focus()
  await page.keyboard.press('Tab')
  const keyboardFocusVisible = await page.evaluate(() => document.activeElement !== document.body)
  const result = {
    fixtureRows: 5000,
    filterMs: Math.round(filterMs * 10) / 10,
    keyboardFocusVisible,
    networkRequests,
    pageHtmlBytes,
    screenReaderRolesPresent,
    shellOverlayRendered,
    sortMs: Math.round(sortMs * 10) / 10,
    startupMs: Math.round(startupMs * 10) / 10,
    timestamp: new Date().toISOString(),
  }

  await writeFile(
    resolve(root, 'benchmarks', 'grid-spike.json'),
    `${JSON.stringify(result, null, 2)}\n`,
  )
  console.log(JSON.stringify(result, null, 2))
} finally {
  await browser.close()
  await rm(temporary, { recursive: true, force: true })
}
