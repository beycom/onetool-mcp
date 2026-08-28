import type { PointerEvent as ReactPointerEvent, ReactNode } from 'react'

import { ChevronIcon, DataIcon, InfoIcon, ViewIcon } from './Icons'
import { DOCK_DEFAULTS, DOCK_LIMITS, type DockLayout, type DockName } from './layoutPreferences'

const PANEL_ICON = { data: DataIcon, info: InfoIcon, view: ViewIcon }

export function ResizablePanel({
  children,
  className,
  label,
  layout,
  name,
  onChange,
}: {
  children: ReactNode
  className: string
  label: string
  layout: DockLayout
  name: DockName
  onChange: (layout: DockLayout) => void
}) {
  const vertical = name !== 'data'
  const resize = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.preventDefault()
    const start = vertical ? event.clientX : event.clientY
    const startSize = layout.size
    event.currentTarget.setPointerCapture(event.pointerId)
    const move = (next: PointerEvent) => {
      const delta = name === 'view' ? next.clientX - start : vertical ? start - next.clientX : start - next.clientY
      const limits = DOCK_LIMITS[name]
      onChange({ collapsed: false, size: Math.max(limits[0], Math.min(limits[1], startSize + delta)) })
    }
    const finish = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', finish)
      window.removeEventListener('pointercancel', finish)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', finish)
    window.addEventListener('pointercancel', finish)
  }
  const style = { [vertical ? 'width' : 'height']: layout.collapsed ? 36 : layout.size }
  const PanelIcon = PANEL_ICON[name]
  const dockLabel = `${label} dock`
  const collapseDirection = name === 'view' ? 'left' : name === 'info' ? 'right' : 'down'
  return (
    <section aria-label={dockLabel} className={`${className} resizable-panel`} data-collapsed={layout.collapsed} style={style}>
      <button
        aria-label={`Resize ${dockLabel.toLowerCase()}`}
        className="panel-resize-handle"
        onDoubleClick={() => onChange({ collapsed: layout.collapsed, size: DOCK_DEFAULTS[name].size })}
        onPointerDown={resize}
        title="Drag to resize; double-click to reset"
        type="button"
      />
      {layout.collapsed ? <div className="panel-rail"><button aria-label={`Open ${dockLabel}`} aria-expanded="false" onClick={() => onChange({ ...layout, collapsed: false })} title={`Open ${dockLabel}`} type="button"><PanelIcon /></button></div> : <div className="panel-content">
        <header className="panel-header"><strong>{label}</strong><button aria-label={`Collapse ${dockLabel}`} aria-expanded="true" className="panel-collapse" onClick={() => onChange({ ...layout, collapsed: true })} title={`Collapse ${dockLabel}`} type="button"><ChevronIcon direction={collapseDirection} /></button></header>
        <div className="panel-body">{children}</div>
      </div>}
    </section>
  )
}
