import { mkdir, readFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { chromium } from 'playwright'

const [reportArgument, snapshotArgument] = process.argv.slice(2)
if (!reportArgument) throw new Error('Usage: test-generated-explorer.mjs REPORT [SNAPSHOT]')

const report = resolve(reportArgument)
const snapshot = resolve(snapshotArgument ?? `${dirname(report)}/explorer-snapshot.png`)
await mkdir(dirname(snapshot), { recursive: true })

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } })
const networkRequests = []
const pageErrors = []
page.on('pageerror', (error) => pageErrors.push(error.message))
await page.route(/https?:\/\//, async (route) => {
  networkRequests.push(route.request().url())
  await route.abort('blockedbyclient')
})

await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' })
await page.goto(pathToFileURL(report).href)
await page.getByRole('main').waitFor()
await page.getByRole('region', { name: 'Architecture diagram' }).waitFor()

const root = page.getByRole('main')
const navigation = page.locator('nav')
const diagram = page.getByRole('region', { name: 'Architecture diagram' })
const nodes = diagram.locator('.react-flow__node[data-id]')

async function nodeIds(scope = diagram) {
  return scope
    .locator('.react-flow__node[data-id]')
    .evaluateAll((items) => items.map((item) => item.getAttribute('data-id')).filter(Boolean).sort())
}

async function waitForNodes(expected, scope = diagram) {
  const sorted = [...expected].sort()
  await page.waitForFunction(
    ({ selector, expectedIds }) => {
      const container = document.querySelector(selector)
      if (!container) return false
      const actual = [...container.querySelectorAll('.react-flow__node[data-id]')]
        .map((item) => item.getAttribute('data-id'))
        .filter(Boolean)
        .sort()
      return JSON.stringify(actual) === JSON.stringify(expectedIds)
    },
    {
      selector:
        scope === diagram
          ? 'section[aria-label="Architecture diagram"]'
          : '[role="dialog"]',
      expectedIds: sorted,
    },
  )
  await page.getByLabel('Laying out solution').waitFor({ state: 'hidden', timeout: 30_000 })
  if (await page.getByRole('alert').filter({ hasText: 'Unable to lay out solution' }).count()) {
    throw new Error('The local LikeC4 layout failed')
  }
}

async function assertNodesFit(scope = diagram) {
  const canvasBounds = await scope.boundingBox()
  if (!canvasBounds) throw new Error('Architecture canvas has no visible bounds')
  const nodeBounds = await scope
    .locator('.react-flow__node[data-id]')
    .evaluateAll((items) => items.map((item) => item.getBoundingClientRect().toJSON()))
  const outside = nodeBounds.filter(
    (bounds) =>
      bounds.left < canvasBounds.x - 1 ||
      bounds.top < canvasBounds.y - 1 ||
      bounds.right > canvasBounds.x + canvasBounds.width + 1 ||
      bounds.bottom > canvasBounds.y + canvasBounds.height + 1,
  )
  if (outside.length > 0) {
    throw new Error(`Architecture canvas did not refit ${outside.length} nodes`)
  }
}

async function selectControl(label, option) {
  await page.getByRole('combobox', { name: label }).click()
  await page.getByRole('option', { name: option, exact: true }).click()
}

async function selectBrowse(group, item) {
  await navigation.getByRole('button', { name: group, exact: true }).click()
  await navigation.getByText(item, { exact: true }).click()
}

await nodes.first().waitFor({ timeout: 30_000 })
const initialGraph = await root.getAttribute('data-active-graph')
if (!initialGraph) throw new Error('Explorer did not expose the active prepared graph')

await page.getByRole('combobox', { name: 'Architectural level' }).click()
const levelOptions = (await page.getByRole('option').allTextContents())
  .map((item) => item.trim())
  .filter(Boolean)
if (JSON.stringify(levelOptions) !== JSON.stringify(['System', 'Application', 'Component'])) {
  throw new Error(`Architectural level includes something other than SYS/APP/CMP: ${levelOptions}`)
}
await page.keyboard.press('Escape')

const roadmap = page.getByRole('combobox', { name: 'Roadmap snapshot' })
await roadmap.click()
const roadmapOptions = page.getByRole('listbox', { name: 'Roadmap snapshot' }).getByRole('option')
const snapshotLabels = await roadmapOptions.allTextContents()
if (snapshotLabels.length !== 3) {
  throw new Error(`Expected base, 2027, and 2028 snapshots; received ${snapshotLabels.length}`)
}
await page.keyboard.press('Escape')

await selectControl('Roadmap snapshot', 'Order 0: base')
await waitForNodes(['A', 'D', 'E', 'F', 'G', 'H'])
const baseNodeIds = await nodeIds()
await selectControl('Roadmap snapshot', 'Order 1: arch-v2-change-2027')
await waitForNodes(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'])
await assertNodesFit()
const changedNodeIds = await nodeIds()

await selectControl('Roadmap snapshot', 'Order 0: base')
await selectBrowse('Systems', 'System I')
await page.getByRole('alert').filter({ hasText: 'No elements match this solution' }).waitFor()
await selectControl('Roadmap snapshot', 'Order 1: arch-v2-change-2027')

await selectBrowse('Change groups', 'wave-one')
await waitForNodes(['A', 'B', 'C', 'D'])
const changeGroupNodeIds = await nodeIds()
await selectBrowse('Tags', 'core')
await waitForNodes(['A'])
const tagNodeIds = await nodeIds()
await selectBrowse('System groups', 'payments')
await waitForNodes(['A'])
const systemGroupNodeIds = await nodeIds()
await selectBrowse('Changes', '2027 delivery')
await waitForNodes(['A', 'B', 'C', 'D'])
const changeNodeIds = await nodeIds()
if ((await root.getAttribute('data-active-graph')) !== initialGraph) {
  throw new Error('Browsing a system set changed the prepared roadmap endpoint')
}
await selectBrowse('Systems', 'System A')
await waitForNodes(['A'])
await navigation.getByText('A to D', { exact: true }).waitFor()

await selectControl('Interface depth', '1')
await waitForNodes(['A', 'D'])
const edge = diagram.locator('.react-flow__edge').first()
const activeEdgeIds = JSON.parse((await root.getAttribute('data-active-edges')) ?? '[]')
if (activeEdgeIds.length === 0) throw new Error('The active depth-one projection has no semantic edge')
if ((await edge.count()) === 0) {
  throw new Error(`The renderer omitted active edges: ${JSON.stringify(activeEdgeIds)}`)
}
const systemAEdgeIds = await diagram
  .locator('.react-flow__edge[data-id]')
  .evaluateAll((items) => items.map((item) => item.getAttribute('data-id')).filter(Boolean).sort())
await selectBrowse('Systems', 'System B')
await waitForNodes(['B'])
const systemBEdgeIds = await diagram
  .locator('.react-flow__edge[data-id]')
  .evaluateAll((items) => items.map((item) => item.getAttribute('data-id')).filter(Boolean).sort())
await selectBrowse('Systems', 'System A')
await waitForNodes(['A', 'D'])

await selectControl('Roadmap snapshot', 'Order 0: base')
await waitForNodes(['A', 'D'])
const baseDStatus = await diagram
  .locator('.react-flow__node[data-id="D"]')
  .textContent()
await selectControl('Roadmap snapshot', 'Order 1: arch-v2-change-2027')
await waitForNodes(['A', 'D'])
const changedDStatus = await diagram
  .locator('.react-flow__node[data-id="D"]')
  .textContent()

const systemNode = diagram.locator('.react-flow__node[data-id="A"]')
const beforeColor = await systemNode.locator('[data-likec4-color]').getAttribute('data-likec4-color')
const beforeGeometry = {
  node: await systemNode.getAttribute('style'),
  edge: await edge.locator('path').first().getAttribute('d'),
}
await selectControl('Color by', 'Tag')
const afterColor = await systemNode.locator('[data-likec4-color]').getAttribute('data-likec4-color')
const afterGeometry = {
  node: await systemNode.getAttribute('style'),
  edge: await edge.locator('path').first().getAttribute('d'),
}
if (beforeColor === afterColor) throw new Error('Color mode did not change rendered color')
if (JSON.stringify(beforeGeometry) !== JSON.stringify(afterGeometry)) {
  throw new Error('Color-only change recalculated diagram geometry')
}

await selectControl('Architectural level', 'Application')
await waitForNodes(['A', 'D', 'app-a', 'app-d'])
const applicationNodeIds = await nodeIds()
await selectControl('Architectural level', 'Component')
await waitForNodes(['A', 'D', 'app-a', 'app-d', 'cmp-d'])
const componentNodeIds = await nodeIds()

const downloadPromise = page.waitForEvent('download')
await page.getByRole('button', { name: 'Export solution' }).click()
await page.getByRole('menuitem', { name: 'Draw.io' }).click()
const download = await downloadPromise
const drawioPath = resolve(dirname(snapshot), 'active-projection.drawio')
await download.saveAs(drawioPath)
const drawioContent = await readFile(drawioPath, 'utf8')
const activeSelectionId = await root.getAttribute('data-active-selection')
const drawioExport = await page.evaluate((content) => {
  const document = new DOMParser().parseFromString(content, 'application/xml')
  if (document.querySelector('parsererror')) throw new Error('Downloaded Draw.io XML did not parse')
  const diagram = document.querySelector('diagram')
  if (!diagram) throw new Error('Downloaded Draw.io XML has no diagram')
  const vertices = [...document.querySelectorAll('mxCell[vertex="1"]')]
  const edges = [...document.querySelectorAll('mxCell[edge="1"]')]
  return {
    nodeIds: vertices.map((item) => item.getAttribute('id')).filter(Boolean).sort(),
    edgeIds: edges.map((item) => item.getAttribute('id')).filter(Boolean).sort(),
    parentById: Object.fromEntries(vertices.map((item) => [item.getAttribute('id'), item.getAttribute('parent')])),
    interfaceIds: edges.flatMap((item) => (item.getAttribute('interfaceIds') ?? '').split(',').filter(Boolean)).sort(),
    selection: JSON.parse(diagram.getAttribute('selection') ?? '{}'),
    selectionId: diagram.getAttribute('selectionId'),
    pageName: diagram.getAttribute('name'),
    hasGeometry: vertices.every((item) => item.querySelector(':scope > mxGeometry')),
    waypointCount: document.querySelectorAll('mxCell[edge="1"] mxPoint').length,
    nodeAStyle: document.querySelector('mxCell[id="A"]')?.getAttribute('style'),
    embedsImage: Boolean(document.querySelector('image, svg')),
  }
}, drawioContent)
if (JSON.stringify(drawioExport.nodeIds) !== JSON.stringify(componentNodeIds)) {
  throw new Error(`Draw.io nodes did not match the active projection: ${JSON.stringify(drawioExport.nodeIds)}`)
}
if (drawioExport.selection.interface_depth !== 1 || drawioExport.selection.level !== 'component') {
  throw new Error('Draw.io selection metadata did not match active depth and level')
}
if (drawioExport.selection.color_by !== 'tag' || drawioExport.selection.order !== 1) {
  throw new Error('Draw.io selection metadata did not match active color and snapshot')
}
if (drawioExport.selection.compare_from !== undefined) {
  throw new Error('Draw.io selection inherited an unrequested snapshot comparison')
}
if (drawioExport.selectionId !== activeSelectionId) {
  throw new Error('Draw.io selection identity did not match the active solution')
}
if (drawioExport.pageName !== '2027 delivery · System: System A · Component · depth 1') {
  throw new Error(`Draw.io page name did not describe the active solution: ${drawioExport.pageName}`)
}
if (drawioExport.selectionId !== 'selection-736ee4371dab3235') {
  throw new Error(`Draw.io selection identity diverged from the API: ${drawioExport.selectionId}`)
}
if (drawioExport.parentById['app-a'] !== 'A' || drawioExport.parentById['cmp-d'] !== 'app-d') {
  throw new Error('Draw.io containment did not match the active projection')
}
if (!drawioExport.interfaceIds.includes('arch-v2-interface-a-to-d')) {
  throw new Error('Draw.io did not retain the active canonical interface identity')
}
if (!drawioExport.hasGeometry || drawioExport.waypointCount < 2 || drawioExport.embedsImage) {
  throw new Error('Draw.io did not contain editable neutral geometry')
}

const back = page.getByRole('button', { name: 'Back in solution history' })
if (!(await back.isEnabled())) throw new Error('Solution history did not record control changes')
await back.click()
await waitForNodes(['A', 'D', 'app-a', 'app-d'])
if (!(await page.getByRole('button', { name: 'Forward in solution history' }).isEnabled())) {
  throw new Error('Forward solution history was not enabled after navigating back')
}

await page.getByRole('button', { name: 'Open full explorer' }).click()
const fullExplorer = page.getByRole('dialog', { name: 'Full solution explorer' })
await fullExplorer.waitFor()
await waitForNodes(['A', 'D', 'app-a', 'app-d'], fullExplorer)
await fullExplorer.locator('.react-flow__node[data-id="app-a"]').click()
const fullDetails = fullExplorer.getByRole('complementary', { name: 'Full explorer details' })
await fullDetails.getByText('Properties', { exact: true }).waitFor()
await fullDetails.getByText('Relationships', { exact: true }).waitFor()
await fullDetails.getByText('A to D', { exact: true }).waitFor()
await page.keyboard.press('Escape')
await fullExplorer.waitFor({ state: 'hidden' })

await page.getByRole('button', { name: 'Show data' }).click()
await page.getByTestId('architecture-grid').waitFor()
await page.getByRole('grid').waitFor()
await page.getByRole('tab', { name: /Included interfaces/ }).click()
await page.getByRole('searchbox', { name: 'Search included interfaces' }).fill('arch-v2-interface-a-to-d')
const interfaceRow = page.locator('.ag-row').filter({ hasText: 'arch-v2-interface-a-to-d' }).first()
if ((await interfaceRow.count()) !== 1) throw new Error('The canonical interface row was not rendered')
await interfaceRow.click()
const inspector = page.getByRole('complementary', { name: 'Selection details' })
await inspector.waitFor()
await inspector.getByText('Integration type: api', { exact: true }).waitFor()
await inspector.getByText('Properties', { exact: true }).waitFor()

const restoredNodeIds = await nodeIds()
const restoredHash = new URL(page.url()).hash
await page.reload()
await page.getByRole('main').waitFor()
await waitForNodes(restoredNodeIds)
if (new URL(page.url()).hash !== restoredHash) throw new Error('URL restoration changed the solution fragment')

await page.getByRole('button', { name: 'Color scheme' }).click()
await page.getByRole('menuitem', { name: 'Dark' }).click()
if ((await page.locator('html').getAttribute('data-mantine-color-scheme')) !== 'dark') {
  throw new Error('Dark theme did not apply to the shared provider')
}

await page.setViewportSize({ width: 390, height: 844 })
await page.getByRole('main').waitFor()
await page.emulateMedia({ media: 'print' })
const toolbarPrintDisplay = await page.locator('.canvas-toolbar').evaluate(
  (element) => getComputedStyle(element).display,
)
if (toolbarPrintDisplay !== 'none') throw new Error('Print state did not hide interactive overlays')
await page.emulateMedia({ media: 'screen', colorScheme: 'dark', reducedMotion: 'reduce' })
await page.setViewportSize({ width: 1600, height: 1000 })
await page.screenshot({ path: snapshot, fullPage: true })

const result = {
  snapshotLabels,
  baseNodeIds,
  changedNodeIds,
  applicationNodeIds,
  componentNodeIds,
  changeGroupNodeIds,
  changeNodeIds,
  tagNodeIds,
  systemGroupNodeIds,
  systemAEdgeIds,
  systemBEdgeIds,
  baseDStatus,
  changedDStatus,
  colorGeometryStable: JSON.stringify(beforeGeometry) === JSON.stringify(afterGeometry),
  fullExplorerDetails: true,
  historyNavigation: true,
  emptyState: true,
  urlRestoration: true,
  interfaceRowFound: (await interfaceRow.count()) > 0,
  drawioExport,
  drawioPath,
  networkRequests,
  pageErrors,
  snapshot,
}
await browser.close()

if (networkRequests.length) throw new Error(`Explorer requested network resources: ${networkRequests.join(', ')}`)
if (pageErrors.length) throw new Error(`Explorer page errors: ${pageErrors.join('; ')}`)
console.log(JSON.stringify(result))
