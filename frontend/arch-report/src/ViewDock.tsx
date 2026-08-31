import { useState } from 'react'

import { CopyIcon, ViewIcon } from './Icons'
import { configuredUserChoice } from './layoutConfig'
import { registeredLayoutMethods, type LayoutMethod } from './layout'
import type { Aspect, ReportPayload, View } from './types'

export function ViewDock({ canvasActive, copyStatus, layoutMethod, legend, matchedCount, onCanvas, onCopy, onLayout, onView, payload, view }: {
  canvasActive: boolean
  copyStatus: string
  layoutMethod: LayoutMethod
  legend: Array<{ tag: string; count: number }>
  matchedCount: number
  onCanvas: () => void
  onCopy: () => void
  onLayout: (method: LayoutMethod) => void
  onView: (change: Partial<View>) => void
  payload: ReportPayload
  view: View
}) {
  const timeline = payload.timelines[view.timeline]
  const milestoneById = new Map(payload.milestones.map((milestone) => [milestone.id, milestone]))
  const selectedTags = new Set(view.lens)
  const [showAllTags, setShowAllTags] = useState(false)
  const rankedTags = [...legend].sort((left, right) => right.count - left.count || left.tag.localeCompare(right.tag))
  const visibleTags = showAllTags || rankedTags.length <= 5
    ? rankedTags
    : rankedTags.filter(({ tag }, index) => index < 5 || selectedTags.has(tag))
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
          {payload.timelines.length > 1 ? <label><span>Timeline</span><select aria-label="Timeline" onChange={(event) => onView({ timeline: Number(event.target.value), position: 0 })} value={view.timeline}>{payload.timelines.map((item, index) => <option key={item.id ?? 'implicit'} value={index}>{item.id ?? 'Default'}</option>)}</select></label> : null}
          {timeline.milestones.length ? <label><span>Stage</span><select aria-label="Stage" onChange={(event) => onView({ position: Number(event.target.value) })} value={view.position}><option value={0}>0 · Base</option>{timeline.milestones.map((id, index) => <option key={id} value={index + 1}>{index + 1} · {milestoneById.get(id)?.name ?? id}</option>)}</select></label> : null}
          <label><span>Relationship</span><select aria-label="Relationship" onChange={(event) => onView({ aspect: event.target.value as Aspect })} value={view.aspect}><option value="call-direction">Calls</option><option value="data-flow">Data flow</option><option value="ownership">Ownership</option></select></label>
          {configuredUserChoice(payload.layout) ? <label><span>Layout</span><select aria-label="Layout" onChange={(event) => onLayout(event.target.value as LayoutMethod)} value={layoutMethod}>{registeredLayoutMethods.map((method) => <option key={method} value={method}>{method[0].toUpperCase() + method.slice(1)}</option>)}</select></label> : null}
          {legend.length ? <fieldset className="tag-control"><legend>Tags</legend><div className="tag-list">{visibleTags.map(({ tag, count }) => <button aria-pressed={selectedTags.has(tag)} key={tag} onClick={() => toggleTag(tag)} type="button"><span>{tag}</span><b>{count}</b></button>)}</div>{rankedTags.length > 5 ? <button aria-expanded={showAllTags} className="show-tags" onClick={() => setShowAllTags((value) => !value)} type="button">{showAllTags ? 'Show fewer' : `Show all ${rankedTags.length}`}</button> : null}{view.lens.length ? <><p aria-live="polite" className="tag-match-count">{view.lens.length} {view.lens.length === 1 ? 'tag' : 'tags'} · {matchedCount} {matchedCount === 1 ? 'entity' : 'entities'} matched</p><button className="clear-tags" onClick={() => onView({ lens: [] })} type="button">Clear tags</button></> : null}</fieldset> : null}
        </section>
      </div>
      <footer className="view-dock-footer"><button onClick={onCopy} type="button"><CopyIcon /><span>Copy view link</span></button><span aria-live="polite">{copyStatus}</span></footer>
    </div>
  )
}
