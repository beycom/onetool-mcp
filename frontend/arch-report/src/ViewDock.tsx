import { CopyIcon, ViewIcon } from './Icons'
import { configuredUserChoice } from './layoutConfig'
import { registeredLayoutMethods, type LayoutMethod } from './layout'
import type { Aspect, Level, ReportPayload, View } from './types'
import { expansionPreset } from './view'

const DETAILS: Array<[Level, string]> = [
  ['systems', 'System'],
  ['subsystems', 'Subsystem'],
  ['containers', 'Container'],
  ['components', 'Component'],
]

export function ViewDock({ canvasActive, copyStatus, layoutMethod, legend, onCanvas, onCopy, onLayout, onPreset, onView, payload, view }: {
  canvasActive: boolean
  copyStatus: string
  layoutMethod: LayoutMethod
  legend: Array<{ tag: string; count: number }>
  onCanvas: () => void
  onCopy: () => void
  onLayout: (method: LayoutMethod) => void
  onPreset: (preset: Level) => void
  onView: (change: Partial<View>) => void
  payload: ReportPayload
  view: View
}) {
  const timeline = payload.timelines[view.timeline]
  const milestoneById = new Map(payload.milestones.map((milestone) => [milestone.id, milestone]))
  const details = payload.rows.subsystems.length
    ? DETAILS
    : DETAILS.filter(([level]) => level !== 'subsystems')
  const selectedTags = new Set(view.lens)
  const selectedDetail = expansionPreset(payload, view.expand)
  const toggleTag = (tag: string) => {
    const next = new Set(selectedTags)
    if (next.has(tag)) next.delete(tag)
    else next.add(tag)
    onView({ lens: next.size === legend.length ? [] : [...next].sort() })
  }
  return (
    <div className="view-dock-body">
      <div className="view-dock-scroll">
        <details className="diagram-group" open>
          <summary>Architecture</summary>
          <button aria-current={canvasActive ? 'page' : undefined} onClick={onCanvas} type="button"><ViewIcon /><span><strong>Canvas</strong><small>Model map</small></span></button>
        </details>
        <section className="view-controls">
          <label><span>Detail</span><select aria-label="Detail" onChange={(event) => onPreset(event.target.value as Level)} value={selectedDetail}>{selectedDetail === 'custom' ? <option value="custom">Custom</option> : null}{details.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          {payload.timelines.length > 1 ? <label><span>Timeline</span><select aria-label="Timeline" onChange={(event) => onView({ timeline: Number(event.target.value), position: 0 })} value={view.timeline}>{payload.timelines.map((item, index) => <option key={item.id ?? 'implicit'} value={index}>{item.id ?? 'Default'}</option>)}</select></label> : null}
          {timeline.milestones.length ? <label><span>Stage</span><select aria-label="Stage" onChange={(event) => onView({ position: Number(event.target.value) })} value={view.position}><option value={0}>0 · Base</option>{timeline.milestones.map((id, index) => <option key={id} value={index + 1}>{index + 1} · {milestoneById.get(id)?.name ?? id}</option>)}</select></label> : null}
          <label><span>Relationship</span><select aria-label="Relationship" onChange={(event) => onView({ aspect: event.target.value as Aspect })} value={view.aspect}><option value="call-direction">Calls</option><option value="data-flow">Data flow</option><option value="ownership">Ownership</option></select></label>
          {configuredUserChoice(payload.layout) ? <label><span>Layout</span><select aria-label="Layout" onChange={(event) => onLayout(event.target.value as LayoutMethod)} value={layoutMethod}>{registeredLayoutMethods.map((method) => <option key={method} value={method}>{method[0].toUpperCase() + method.slice(1)}</option>)}</select></label> : null}
          {legend.length ? <fieldset className="tag-control"><legend>Tags</legend><div className="tag-list">{legend.map(({ tag, count }) => <button aria-pressed={selectedTags.has(tag)} key={tag} onClick={() => toggleTag(tag)} type="button"><span>{tag}</span><b>{count}</b></button>)}</div>{view.lens.length ? <button className="clear-tags" onClick={() => onView({ lens: [] })} type="button">Clear tags</button> : null}</fieldset> : null}
        </section>
      </div>
      <footer className="view-dock-footer"><button onClick={onCopy} type="button"><CopyIcon /><span>Copy view link</span></button><span aria-live="polite">{copyStatus}</span></footer>
    </div>
  )
}
