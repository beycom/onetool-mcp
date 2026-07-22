import { readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const dist = resolve(root, 'dist')
const files = readdirSync(dist, { recursive: true }).filter((entry) => typeof entry === 'string')

if (files.length !== 1 || files[0] !== 'index.html') {
  throw new Error(`Offline build must contain only index.html; received ${files.join(', ')}`)
}

const html = readFileSync(resolve(dist, 'index.html'), 'utf8')
const externalAttributes = [
  ...html.matchAll(/<(?:script|link|img)\b[^>]*(?:src|href)=["']([^"']+)["']/gi),
].map((match) => match[1])
const remote = externalAttributes.filter((value) => /^(?:https?:)?\/\//i.test(value))

if (remote.length > 0) {
  throw new Error(`Offline build contains remote assets: ${remote.join(', ')}`)
}
if (!html.includes('Content-Security-Policy')) {
  throw new Error('Offline build is missing its Content Security Policy')
}
if (!html.includes('IBM Plex Sans')) {
  throw new Error('Offline build does not contain the local IBM Plex Sans asset')
}

console.log(`Verified self-contained offline build (${Buffer.byteLength(html)} bytes)`)
