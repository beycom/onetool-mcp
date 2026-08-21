import { useMemo, useState } from 'react'

import {
  passports,
  sequenceMessages,
  sequenceParticipants,
  type DiagramMode,
  type PassportRecord,
} from './data'
import { useDraggablePanel } from './useDraggablePanel'
import { ZenUmlSequenceDiagram } from './ZenUmlSequenceDiagram'
import {
  checkoutSequenceFixture,
  stressSequenceFixture,
  type SequenceFixture,
} from './zenumlSequence'

const participantById = new Map<string, (typeof sequenceParticipants)[number]>(
  sequenceParticipants.map((participant) => [participant.id, participant]),
)

type SequenceRenderer = 'native' | 'zenuml'
type SequenceScenario = 'checkout' | 'stress'

function spikePassport(fixture: SequenceFixture, canonicalId: string): PassportRecord | undefined {
  if (passports[canonicalId]) return passports[canonicalId]

  const participant = fixture.participants.find((candidate) => candidate.id === canonicalId)
  if (participant) {
    const incoming = fixture.messages.filter((message) => message.to === canonicalId).length
    const outgoing = fixture.messages.filter((message) => message.from === canonicalId).length
    return {
      id: participant.id,
      name: participant.label,
      subtitle: participant.subtitle ?? 'ZenUML stress participant',
      kind: 'service',
      technology: 'Generated spike fixture',
      context: fixture.title,
      tags: ['PARTICIPANT', 'ZEN-UML', 'SPIKE'],
      incoming,
      outgoing,
      upstream: incoming,
      downstream: outgoing,
      note: 'Ephemeral stress-fixture identity; not part of the production architecture model.',
      relationships: [],
    }
  }

  const messageIndex = fixture.messages.findIndex((candidate) => candidate.id === canonicalId)
  const message = fixture.messages[messageIndex]
  if (!message) return undefined
  const source = fixture.participants.find((candidate) => candidate.id === message.from)
  const target = fixture.participants.find((candidate) => candidate.id === message.to)
  return {
    id: message.id,
    name: message.label,
    subtitle: `${source?.label ?? message.from} → ${target?.label ?? message.to}`,
    kind: 'message',
    technology: message.kind === 'return' ? 'Return message' : message.kind === 'async' ? 'Asynchronous message' : 'Synchronous message',
    context: `${fixture.title} · step ${messageIndex + 1}`,
    tags: ['MESSAGE', message.kind, 'ZEN-UML', 'SPIKE'],
    incoming: 1,
    outgoing: 1,
    upstream: messageIndex,
    downstream: fixture.messages.length - messageIndex - 1,
    note: 'Ephemeral stress-fixture identity used to test rendered SVG annotation.',
    relationships: [],
  }
}

export function SequenceCanvas({
  mode,
  onModeChange,
  onSelect,
  selectedId,
}: {
  mode: DiagramMode
  onModeChange: (mode: DiagramMode) => void
  onSelect: (passport: PassportRecord) => void
  selectedId?: string
}) {
  const [scale, setScale] = useState(86)
  const [step, setStep] = useState(0)
  const [renderer, setRenderer] = useState<SequenceRenderer>('zenuml')
  const [scenario, setScenario] = useState<SequenceScenario>('checkout')
  const { dragHandleProps, panelRef } = useDraggablePanel<HTMLElement>('journey probe')
  const fixture = scenario === 'checkout' ? checkoutSequenceFixture : stressSequenceFixture
  const selectedMessage = fixture.messages.findIndex((message) => message.id === selectedId)
  const currentStep = selectedMessage >= 0 ? selectedMessage : step
  const messageOpacity = useMemo(() => new Map(sequenceMessages.map((message, index) => {
    if (mode === 'map') return [message.id, 1]
    if (mode === 'path') return [message.id, message.route ? 1 : 0.14]
    return [message.id, index === currentStep ? 1 : 0.16]
  })), [currentStep, mode])

  const selectCanonicalId = (canonicalId: string) => {
    const messageIndex = fixture.messages.findIndex((message) => message.id === canonicalId)
    if (messageIndex >= 0) setStep(messageIndex)
    const record = spikePassport(fixture, canonicalId)
    if (record) onSelect(record)
  }

  const selectStep = (index: number) => {
    const normalized = Math.max(0, Math.min(fixture.messages.length - 1, index))
    setStep(normalized)
    const record = spikePassport(fixture, fixture.messages[normalized].id)
    if (record) onSelect(record)
  }

  const selectScenario = (next: SequenceScenario) => {
    setScenario(next)
    setStep(0)
    const nextFixture = next === 'checkout' ? checkoutSequenceFixture : stressSequenceFixture
    const record = spikePassport(nextFixture, nextFixture.messages[0].id)
    if (record) onSelect(record)
  }

  const selectRenderer = (next: SequenceRenderer) => {
    setRenderer(next)
    if (next === 'native' && scenario === 'stress') selectScenario('checkout')
  }

  return (
    <div className="canvas-stage sequence-stage" data-mode={mode}>
      <div className="canvas-context">
        <span className="context-kicker">SEQUENCE · {renderer === 'zenuml' ? 'ZENUML SPIKE' : 'NATIVE CONTROL'}</span>
        <strong>{fixture.title}</strong>
        <span>{fixture.participants.length} participants · {fixture.messages.length} authored messages</span>
      </div>

      <section aria-label="Sequence renderer spike controls" className="sequence-spike-controls">
        <div>
          <span>Renderer</span>
          <button aria-pressed={renderer === 'zenuml'} onClick={() => selectRenderer('zenuml')} type="button">ZenUML</button>
          <button aria-pressed={renderer === 'native'} onClick={() => selectRenderer('native')} type="button">Native control</button>
        </div>
        <div>
          <span>Fixture</span>
          <button aria-pressed={scenario === 'checkout'} onClick={() => selectScenario('checkout')} type="button">Checkout</button>
          <button
            aria-pressed={scenario === 'stress'}
            disabled={renderer === 'native'}
            onClick={() => selectScenario('stress')}
            type="button"
          >12 × 100</button>
        </div>
      </section>

      {mode === 'path' ? (
        <section aria-label="Sequence route probe" className="draggable-panel route-probe sequence-probe" ref={panelRef}>
          <header>
            <div>
              <span className="panel-kicker">JOURNEY PROBE</span>
              <strong>{fixture.title}</strong>
            </div>
            <div className="panel-header-actions">
              <button className="panel-drag-handle" type="button" {...dragHandleProps}><span aria-hidden="true">⠿</span></button>
              <button onClick={() => onModeChange('map')} type="button">Clear</button>
            </div>
          </header>
          <div className="route-steps compact">
            {fixture.participants.map((participant, index) => (
              <span className="route-step-wrap" key={participant.id}>
                <button onClick={() => selectCanonicalId(participant.id)} type="button">{participant.label}</button>
                {index < fixture.participants.length - 1 ? <span aria-hidden="true">→</span> : null}
              </span>
            ))}
          </div>
          <footer>{fixture.messages.length} ordered messages · {fixture.fragments.length} interaction fragments · authored journey</footer>
        </section>
      ) : null}

      <div className="sequence-scroll" data-renderer={renderer}>
        {renderer === 'native' ? <svg
          aria-label="Checkout authorization sequence diagram"
          className="sequence-diagram"
          role="img"
          style={{ width: `${scale}%` }}
          viewBox="0 0 1340 880"
        >
          <defs>
            <marker id="sequence-arrow" markerHeight="8" markerWidth="9" orient="auto" refX="8" refY="4">
              <path d="M0,0 L9,4 L0,8 z" fill="currentColor" />
            </marker>
            <marker id="sequence-open-arrow" markerHeight="8" markerWidth="9" orient="auto" refX="8" refY="4">
              <path d="M0,0 L9,4 L0,8" fill="none" stroke="currentColor" strokeWidth="1.5" />
            </marker>
          </defs>

          <rect className="sequence-fragment" height="258" rx="12" width="740" x="520" y="430" />
          <path className="fragment-tab" d="M520 430h140l20 26H520z" />
          <text className="fragment-title" x="535" y="450">alt · payment approved</text>

          {sequenceParticipants.map((participant) => (
            <g
              className="sequence-participant"
              data-selected={selectedId === participant.id ? 'true' : 'false'}
              key={participant.id}
              onClick={() => onSelect(passports[participant.id])}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') onSelect(passports[participant.id])
              }}
              role="button"
              tabIndex={0}
            >
              <rect className={`participant-card tone-${participant.tone}`} height="82" rx="12" width="178" x={participant.x - 89} y="52" />
              <text className="participant-title" textAnchor="middle" x={participant.x} y="88">{participant.label}</text>
              <text className="participant-subtitle" textAnchor="middle" x={participant.x} y="112">{participant.subtitle}</text>
              <line className="lifeline" x1={participant.x} x2={participant.x} y1="134" y2="840" />
            </g>
          ))}

          <rect className="activation tone-teal" height="508" rx="4" width="14" x="543" y="242" />
          <rect className="activation tone-violet" height="78" rx="4" width="14" x="993" y="476" />
          <rect className="activation tone-slate" height="92" rx="4" width="14" x="1218" y="545" />

          {sequenceMessages.map((message, index) => {
            const source = participantById.get(message.from)
            const target = participantById.get(message.to)
            if (!source || !target) return null
            const reverse = source.x > target.x
            const labelX = Math.min(source.x, target.x) + Math.abs(target.x - source.x) / 2
            const active = selectedId === message.id || (mode === 'lens' && currentStep === index)
            return (
              <g
                className="sequence-message"
                data-active={active ? 'true' : 'false'}
                key={message.id}
                onClick={() => selectStep(index)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') selectStep(index)
                }}
                opacity={messageOpacity.get(message.id)}
                role="button"
                tabIndex={0}
              >
                <text className="message-number" x={reverse ? source.x - 19 : source.x + 19} y={message.y - 9}>{index + 1}</text>
                <text className="message-label" textAnchor="middle" x={labelX} y={message.y - 12}>{message.label}</text>
                <line
                  className={message.kind === 'return' ? 'message-line return-line' : 'message-line'}
                  markerEnd={message.kind === 'return' ? 'url(#sequence-open-arrow)' : 'url(#sequence-arrow)'}
                  x1={source.x}
                  x2={target.x}
                  y1={message.y}
                  y2={message.y}
                />
              </g>
            )
          })}
        </svg> : (
          <ZenUmlSequenceDiagram
            currentStep={currentStep}
            fixture={fixture}
            mode={mode}
            onSelect={selectCanonicalId}
            scale={scale}
            selectedId={selectedId}
          />
        )}
      </div>

      <aside aria-label="Sequence radar" className="sequence-radar">
        <header><span className="status-dot" /> SEMANTIC RADAR</header>
        <div className="radar-body">
          {fixture.messages.map((message, index) => (
            <button
              aria-label={`Go to step ${index + 1}: ${message.label}`}
              data-active={index === currentStep ? 'true' : 'false'}
              key={message.id}
              onClick={() => selectStep(index)}
              style={{ top: `${8 + index * (84 / Math.max(1, fixture.messages.length - 1))}%` }}
              type="button"
            />
          ))}
        </div>
      </aside>

      <nav aria-label="Sequence navigation" className="navigation-rail">
        <div className="mode-switch">
          {(['path', 'map', 'lens'] as const).map((item) => (
            <button aria-pressed={mode === item} key={item} onClick={() => onModeChange(item)} type="button">
              {item.toUpperCase()}
            </button>
          ))}
        </div>
        <span className="rail-separator" />
        <button aria-label="Previous message" onClick={() => selectStep(currentStep - 1)} type="button">←</button>
        <output>STEP {currentStep + 1}/{fixture.messages.length}</output>
        <button aria-label="Next message" onClick={() => selectStep(currentStep + 1)} type="button">→</button>
        <span className="rail-separator" />
        <button aria-label="Zoom out" onClick={() => setScale((value) => Math.max(60, value - 10))} type="button">−</button>
        <output>READ {scale}%</output>
        <button aria-label="Zoom in" onClick={() => setScale((value) => Math.min(120, value + 10))} type="button">+</button>
      </nav>
    </div>
  )
}
