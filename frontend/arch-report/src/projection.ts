import type { ProjectedState, ReportPayload, ReportRow, View } from './types'

function contains(row: ReportRow, timeline: number, position: number) {
  return row.intervals[timeline].live.some(([start, end]) => (
    start <= position && (end === null || position < end)
  ))
}

export function projectState(payload: ReportPayload, view: View): ProjectedState {
  const systems = payload.rows.systems.filter((row) => contains(row, view.timeline, view.position))
  const systemIds = new Set(systems.map((row) => row.id))
  const interfaces = payload.rows.interfaces.filter((row) => (
    contains(row, view.timeline, view.position)
    && Boolean(row.provider && row.consumer && systemIds.has(row.provider) && systemIds.has(row.consumer))
  ))
  const relationships = payload.rows.relationships.filter((row) => (
    contains(row, view.timeline, view.position)
    && Boolean(row.source && row.target && systemIds.has(row.source) && systemIds.has(row.target))
  ))
  return { systems, interfaces, relationships }
}
