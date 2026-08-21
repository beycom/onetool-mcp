import {
  useCallback,
  useEffect,
  useRef,
  type KeyboardEventHandler,
  type PointerEventHandler,
} from 'react'

type Point = { x: number; y: number }

const EDGE_GAP = 8
const KEYBOARD_STEP = 8
const KEYBOARD_LARGE_STEP = 24

function clamp(value: number, minimum: number, maximum: number) {
  if (maximum < minimum) return 0
  return Math.min(maximum, Math.max(minimum, value))
}

export function useDraggablePanel<T extends HTMLElement>(name: string) {
  const panelRef = useRef<T | null>(null)
  const offsetRef = useRef<Point>({ x: 0, y: 0 })
  const dragRef = useRef<{
    offset: Point
    pointerId: number
    start: Point
  } | null>(null)

  const constrain = useCallback((point: Point): Point => {
    const panel = panelRef.current
    if (!panel) return point

    const parent = panel.offsetParent as HTMLElement | null
    const parentRect = parent?.getBoundingClientRect() ?? {
      bottom: window.innerHeight,
      left: 0,
      right: window.innerWidth,
      top: 0,
    }
    const panelRect = panel.getBoundingClientRect()
    const baseLeft = panelRect.left - offsetRef.current.x
    const baseTop = panelRect.top - offsetRef.current.y

    return {
      x: clamp(
        point.x,
        parentRect.left + EDGE_GAP - baseLeft,
        parentRect.right - EDGE_GAP - panelRect.width - baseLeft,
      ),
      y: clamp(
        point.y,
        parentRect.top + EDGE_GAP - baseTop,
        parentRect.bottom - EDGE_GAP - panelRect.height - baseTop,
      ),
    }
  }, [])

  const applyOffset = useCallback((point: Point) => {
    offsetRef.current = point
    panelRef.current?.style.setProperty('--drag-x', `${point.x}px`)
    panelRef.current?.style.setProperty('--drag-y', `${point.y}px`)
  }, [])

  const moveTo = useCallback((point: Point) => {
    applyOffset(constrain(point))
  }, [applyOffset, constrain])

  const reset = useCallback(() => applyOffset({ x: 0, y: 0 }), [applyOffset])

  useEffect(() => {
    const keepInBounds = () => moveTo(offsetRef.current)
    const observer = new ResizeObserver(keepInBounds)
    if (panelRef.current) observer.observe(panelRef.current)
    window.addEventListener('resize', keepInBounds)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', keepInBounds)
    }
  }, [moveTo])

  const onPointerDown: PointerEventHandler<HTMLButtonElement> = useCallback((event) => {
    if (event.button !== 0) return
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    dragRef.current = {
      offset: offsetRef.current,
      pointerId: event.pointerId,
      start: { x: event.clientX, y: event.clientY },
    }
    if (panelRef.current) panelRef.current.dataset.dragging = 'true'
  }, [])

  const onPointerMove: PointerEventHandler<HTMLButtonElement> = useCallback((event) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    moveTo({
      x: drag.offset.x + event.clientX - drag.start.x,
      y: drag.offset.y + event.clientY - drag.start.y,
    })
  }, [moveTo])

  const finishDragging = useCallback((pointerId: number) => {
    if (dragRef.current?.pointerId !== pointerId) return
    dragRef.current = null
    if (panelRef.current) delete panelRef.current.dataset.dragging
  }, [])

  const onPointerUp: PointerEventHandler<HTMLButtonElement> = useCallback((event) => {
    finishDragging(event.pointerId)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }, [finishDragging])

  const onPointerCancel: PointerEventHandler<HTMLButtonElement> = useCallback((event) => {
    finishDragging(event.pointerId)
  }, [finishDragging])

  const onKeyDown: KeyboardEventHandler<HTMLButtonElement> = useCallback((event) => {
    const step = event.shiftKey ? KEYBOARD_LARGE_STEP : KEYBOARD_STEP
    const delta = {
      ArrowDown: { x: 0, y: step },
      ArrowLeft: { x: -step, y: 0 },
      ArrowRight: { x: step, y: 0 },
      ArrowUp: { x: 0, y: -step },
    }[event.key]

    if (event.key === 'Home') {
      event.preventDefault()
      reset()
    } else if (delta) {
      event.preventDefault()
      moveTo({ x: offsetRef.current.x + delta.x, y: offsetRef.current.y + delta.y })
    }
  }, [moveTo, reset])

  return {
    dragHandleProps: {
      'aria-keyshortcuts': 'ArrowUp ArrowDown ArrowLeft ArrowRight Home',
      'aria-label': `Move ${name}`,
      onDoubleClick: reset,
      onKeyDown,
      onPointerCancel,
      onPointerDown,
      onPointerMove,
      onPointerUp,
      title: 'Drag to move · arrow keys move · double-click resets',
    },
    panelRef,
  }
}
