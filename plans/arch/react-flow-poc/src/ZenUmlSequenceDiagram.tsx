import { useEffect, useLayoutEffect, useRef, useState } from 'react'

import type { DiagramMode } from './data'
import {
  compileZenUml,
  type SequenceFixture,
  type ZenUmlCompilation,
  type ZenUmlEventBinding,
} from './zenumlSequence'

interface MappingReport {
  eventsMapped: number
  participantsMapped: number
  totalEvents: number
  totalParticipants: number
}

interface RenderedSpike {
  compilation: ZenUmlCompilation
  loadMs: number
  durationMs: number
  error?: string
  height: number
  svg: string
  width: number
}

function bindingQueue(bindings: readonly ZenUmlEventBinding[]): Map<string, string[]> {
  const queues = new Map<string, string[]>()
  for (const binding of bindings) {
    const key = `${binding.elementKind}\u0000${binding.renderedLabel}`
    queues.set(key, [...(queues.get(key) ?? []), binding.id])
  }
  return queues
}

export function ZenUmlSequenceDiagram({
  currentStep,
  fixture,
  mode,
  onSelect,
  scale,
  selectedId,
}: {
  currentStep: number
  fixture: SequenceFixture
  mode: DiagramMode
  onSelect: (canonicalId: string) => void
  scale: number
  selectedId?: string
}) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [rendered, setRendered] = useState<RenderedSpike | null>(null)
  const [mapping, setMapping] = useState<MappingReport | null>(null)

  useEffect(() => {
    let current = true
    setRendered(null)
    setMapping(null)

    const render = async () => {
      const compilation = compileZenUml(fixture)
      const loadStartedAt = performance.now()
      try {
        const { renderToSvg } = await import('@zenuml/core')
        const loadedAt = performance.now()
        const result = renderToSvg(compilation.source)
        if (!current) return
        setRendered({
          compilation,
          loadMs: loadedAt - loadStartedAt,
          durationMs: performance.now() - loadedAt,
          height: result.height,
          svg: result.svg,
          width: result.width,
        })
      } catch (error) {
        if (!current) return
        setRendered({
          compilation,
          loadMs: performance.now() - loadStartedAt,
          durationMs: 0,
          error: error instanceof Error ? error.message : String(error),
          height: 0,
          svg: '',
          width: 0,
        })
      }
    }

    void render()
    return () => {
      current = false
    }
  }, [fixture])

  useLayoutEffect(() => {
    const host = hostRef.current
    const svg = host?.querySelector('svg')
    if (!host || !svg || !rendered || rendered.error) {
      setMapping(null)
      return
    }

    svg.classList.add('zenuml-rendered-svg')
    svg.setAttribute('aria-label', `${fixture.title} rendered by ZenUML`)
    svg.setAttribute('role', 'group')
    svg.style.width = `${Math.max(880, rendered.width * scale / 100)}px`
    svg.style.height = 'auto'

    let participantsMapped = 0
    for (const participant of svg.querySelectorAll<SVGGElement>('g.participant:not(.participant-bottom)')) {
      const alias = participant.dataset.participant
      const canonicalId = alias ? rendered.compilation.participantIdsByAlias.get(alias) : undefined
      if (!canonicalId) continue
      const model = fixture.participants.find((candidate) => candidate.id === canonicalId)
      participant.dataset.canonicalId = canonicalId
      participant.dataset.selected = selectedId === canonicalId ? 'true' : 'false'
      participant.setAttribute('aria-label', `Participant ${model?.label ?? canonicalId}`)
      participant.setAttribute('role', 'button')
      participant.setAttribute('tabindex', '0')
      participantsMapped += 1
    }

    const queues = bindingQueue(rendered.compilation.eventBindings)
    let eventsMapped = 0
    const labelGroups: Array<{ elementKind: 'message' | 'return'; labels: NodeListOf<SVGTextElement> }> = [
      { elementKind: 'message', labels: svg.querySelectorAll('g.message > .message-label') },
      { elementKind: 'return', labels: svg.querySelectorAll('g.return > .return-label') },
    ]
    const indexByMessageId = new Map(fixture.messages.map((message, index) => [message.id, index]))

    for (const { elementKind, labels } of labelGroups) {
      for (const label of labels) {
        const renderedLabel = label.textContent?.trim() ?? ''
        const queue = queues.get(`${elementKind}\u0000${renderedLabel}`)
        const canonicalId = queue?.shift()
        const group = label.closest<SVGGElement>(`g.${elementKind}`)
        if (!canonicalId || !group) continue
        const message = fixture.messages[indexByMessageId.get(canonicalId) ?? -1]
        const index = indexByMessageId.get(canonicalId) ?? -1
        const opacity = mode === 'map'
          ? 1
          : mode === 'path'
            ? message?.route ? 1 : 0.14
            : index === currentStep ? 1 : 0.16
        group.dataset.canonicalId = canonicalId
        group.dataset.active = selectedId === canonicalId || (mode === 'lens' && index === currentStep) ? 'true' : 'false'
        group.style.opacity = String(opacity)
        group.setAttribute('aria-label', `Step ${index + 1}: ${message?.label ?? renderedLabel}`)
        group.setAttribute('role', 'button')
        group.setAttribute('tabindex', '0')
        eventsMapped += 1
      }
    }

    const selectedElement = [...svg.querySelectorAll<SVGElement>('[data-canonical-id]')]
      .find((element) => element.dataset.canonicalId === selectedId)
    selectedElement?.scrollIntoView({ block: 'center', inline: 'center' })

    const nextMapping = {
      eventsMapped,
      participantsMapped,
      totalEvents: fixture.messages.length,
      totalParticipants: fixture.participants.length,
    }
    setMapping((currentMapping) => (
      currentMapping
      && currentMapping.eventsMapped === nextMapping.eventsMapped
      && currentMapping.participantsMapped === nextMapping.participantsMapped
      && currentMapping.totalEvents === nextMapping.totalEvents
      && currentMapping.totalParticipants === nextMapping.totalParticipants
        ? currentMapping
        : nextMapping
    ))
  }, [currentStep, fixture, mapping, mode, rendered, scale, selectedId])

  const activate = (target: EventTarget | null) => {
    if (!(target instanceof Element)) return
    const canonicalId = target.closest<SVGElement>('[data-canonical-id]')?.dataset.canonicalId
    if (canonicalId) onSelect(canonicalId)
  }

  if (!rendered) {
    return <div aria-live="polite" className="zenuml-loading">Loading the optional ZenUML renderer…</div>
  }

  if (rendered.error) {
    return (
      <section className="zenuml-error" role="alert">
        <strong>ZenUML render failed</strong>
        <pre>{rendered.error}</pre>
      </section>
    )
  }

  const mappingPassed = mapping
    && mapping.eventsMapped === mapping.totalEvents
    && mapping.participantsMapped === mapping.totalParticipants

  return (
    <>
      <aside aria-label="ZenUML spike evidence" className="zenuml-evidence">
        <span><strong>{rendered.loadMs.toFixed(1)} ms</strong> load</span>
        <span><strong>{rendered.durationMs.toFixed(1)} ms</strong> render</span>
        <span><strong>{rendered.width}×{rendered.height}</strong> SVG</span>
        <span data-pass={mappingPassed ? 'true' : 'false'}>
          <strong>{mapping?.eventsMapped ?? 0}/{fixture.messages.length}</strong> event IDs
        </span>
        <span data-pass={mappingPassed ? 'true' : 'false'}>
          <strong>{mapping?.participantsMapped ?? 0}/{fixture.participants.length}</strong> participant IDs
        </span>
      </aside>
      <div
        className="zenuml-host"
        dangerouslySetInnerHTML={{ __html: rendered.svg }}
        onClick={(event) => activate(event.target)}
        onKeyDown={(event) => {
          if (event.key !== 'Enter' && event.key !== ' ') return
          event.preventDefault()
          activate(event.target)
        }}
        ref={hostRef}
      />
    </>
  )
}
