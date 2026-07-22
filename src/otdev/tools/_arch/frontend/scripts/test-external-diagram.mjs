import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { chromium } from 'playwright'

const [reportArgument, diagramName = 'Overview'] = process.argv.slice(2)
if (!reportArgument) throw new Error('Usage: test-external-diagram.mjs REPORT [DIAGRAM_NAME]')

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
const networkRequests = []
const pageErrors = []
page.on('pageerror', (error) => pageErrors.push(error.message))
await page.route(/https?:\/\//, async (route) => {
  networkRequests.push(route.request().url())
  await route.abort('blockedbyclient')
})

await page.goto(pathToFileURL(resolve(reportArgument)).href)
await page.getByRole('main').waitFor()
const control = page.getByRole('combobox', { name: 'Diagram view' })
await control.waitFor()
if ((await control.inputValue()) !== diagramName) {
  throw new Error(`Saved diagram was not restored: ${await control.inputValue()}`)
}
const image = page.getByRole('img', { name: diagramName })
await image.waitFor()
if (!(await image.getAttribute('src'))?.startsWith('data:image/svg+xml;base64,')) {
  throw new Error('External SVG was not rendered from an embedded data URL')
}
if ((await page.locator('.react-flow__node[data-id]').count()) !== 0) {
  throw new Error('Generated diagram nodes remained visible over the external diagram')
}
if (networkRequests.length > 0) throw new Error(`Unexpected network requests: ${networkRequests}`)
if (pageErrors.length > 0) throw new Error(`Browser errors: ${pageErrors}`)

await browser.close()
