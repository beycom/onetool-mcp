import type { PointerEvent as ReactPointerEvent, ReactNode } from 'react'

import { PANEL_DEFAULTS, type PanelLayout, type PanelName } from './layoutPreferences'

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
  layout: PanelLayout
  name: PanelName
  onChange: (layout: PanelLayout) => void
}) {
  const vertical = name !== 'bottom'
  const resize = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.preventDefault()
    const start = vertical ? event.clientX : event.clientY
    const startSize = layout.size
    event.currentTarget.setPointerCapture(event.pointerId)
    const move = (next: PointerEvent) => {
      const delta = vertical ? start - next.clientX : start - next.clientY
      const limits = name === 'side' ? [280, 720] : name === 'legend' ? [180, 400] : [180, 640]
      onChange({ collapsed: false, size: Math.max(limits[0], Math.min(limits[1], startSize + delta)) })
    }
    const finish = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', finish)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', finish)
  }
  const style = { [vertical ? 'width' : 'height']: layout.collapsed ? 34 : layout.size }
  return (
    <section aria-label={label} className={`${className} resizable-panel`} data-collapsed={layout.collapsed} style={style}>
      <button
        aria-label={`Resize ${label.toLowerCase()}`}
        className="panel-resize-handle"
        onDoubleClick={() => onChange({ collapsed: layout.collapsed, size: PANEL_DEFAULTS[name].size })}
        onPointerDown={resize}
        title="Drag to resize; double-click to reset"
        type="button"
      />
      <button
        aria-expanded={!layout.collapsed}
        className="panel-collapse"
        onClick={() => onChange({ ...layout, collapsed: !layout.collapsed })}
        type="button"
      >
        {layout.collapsed ? `Open ${label}` : `Collapse ${label}`}
      </button>
      <div className="panel-content">{layout.collapsed ? null : children}</div>
    </section>
  )
}
