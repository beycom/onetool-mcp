import type { PointerEvent as ReactPointerEvent, ReactNode } from 'react'

import { DOCK_DEFAULTS, DOCK_LIMITS, type DockLayout, type DockName } from './layoutPreferences'

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
  const style = { [vertical ? 'width' : 'height']: layout.collapsed ? 34 : layout.size }
  return (
    <section aria-label={label} className={`${className} resizable-panel`} data-collapsed={layout.collapsed} style={style}>
      <button
        aria-label={`Resize ${label.toLowerCase()}`}
        className="panel-resize-handle"
        onDoubleClick={() => onChange({ collapsed: layout.collapsed, size: DOCK_DEFAULTS[name].size })}
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
