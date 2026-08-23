import fixturePayload from './fixture-payload.json'
import type { ReportPayload } from './types'

export function readPayload(): ReportPayload {
  const element = document.getElementById('arch-payload')
  const content = element?.textContent?.trim()
  if (content && !content.startsWith('__ARCH_')) {
    const payload = JSON.parse(content) as ReportPayload
    if (payload.payload !== 'arch-report/v1') throw new Error('Unsupported report payload')
    return payload
  }
  return fixturePayload as unknown as ReportPayload
}
