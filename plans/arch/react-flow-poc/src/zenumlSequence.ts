import { sequenceMessages, sequenceParticipants } from './data'

export interface SequenceFixtureParticipant {
  id: string
  label: string
  subtitle?: string
}

export interface SequenceFixtureMessage {
  id: string
  from: string
  to: string
  label: string
  kind: 'sync' | 'async' | 'return'
  route: boolean
}

export interface SequenceFixtureFragment {
  id: string
  kind: 'alt' | 'loop'
  condition: string
  startMessageId: string
  endMessageId: string
}

export interface SequenceFixture {
  id: string
  title: string
  participants: readonly SequenceFixtureParticipant[]
  messages: readonly SequenceFixtureMessage[]
  fragments: readonly SequenceFixtureFragment[]
}

export interface ZenUmlEventBinding {
  id: string
  renderedLabel: string
  elementKind: 'message' | 'return'
}

export interface ZenUmlCompilation {
  source: string
  participantIdsByAlias: ReadonlyMap<string, string>
  eventBindings: readonly ZenUmlEventBinding[]
}

interface Interval {
  id: string
  start: number
  end: number
}

const checkoutFragments: readonly SequenceFixtureFragment[] = [
  {
    id: 'approved-path',
    kind: 'alt',
    condition: 'paymentApproved',
    startMessageId: 'm5',
    endMessageId: 'm7',
  },
]

export const checkoutSequenceFixture: SequenceFixture = {
  id: 'checkout',
  title: 'Checkout authorization',
  participants: sequenceParticipants.map(({ id, label, subtitle }) => ({ id, label, subtitle })),
  messages: sequenceMessages.map(({ id, from, to, kind, label, route }) => ({
    id,
    from,
    to,
    kind,
    label,
    route,
  })),
  fragments: checkoutFragments,
}

function createStressFixture(): SequenceFixture {
  const participants: SequenceFixtureParticipant[] = Array.from({ length: 12 }, (_, index) => ({
    id: `stress-p${index + 1}`,
    label: `Service ${index + 1}`,
    subtitle: index % 3 === 0 ? 'edge' : index % 3 === 1 ? 'service' : 'data',
  }))
  const messages: SequenceFixtureMessage[] = []

  for (let index = 0; index < 50; index += 1) {
    const source = participants[index % participants.length]
    const target = participants[(index * 5 + 3) % participants.length]
    const sequence = index + 1
    const isAsync = index % 10 === 4
    messages.push({
      id: `stress-m${index * 2 + 1}`,
      from: source.id,
      to: target.id,
      label: sequence === 7
        ? 'requestWithAnIntentionallyLongLabelToMeasureParticipantAndMessageClearance'
        : `request${sequence}`,
      kind: isAsync ? 'async' : 'sync',
      route: index < 10,
    })
    messages.push({
      id: `stress-m${index * 2 + 2}`,
      from: target.id,
      to: source.id,
      label: `ack${sequence}`,
      kind: 'return',
      route: index < 10,
    })
  }

  return {
    id: 'stress',
    title: 'ZenUML 12 participant / 100 message stress case',
    participants,
    messages,
    fragments: [
      {
        id: 'stress-alt',
        kind: 'alt',
        condition: 'primaryPath',
        startMessageId: 'stress-m21',
        endMessageId: 'stress-m80',
      },
      {
        id: 'stress-loop',
        kind: 'loop',
        condition: 'retryBudgetRemaining',
        startMessageId: 'stress-m31',
        endMessageId: 'stress-m60',
      },
    ],
  }
}

export const stressSequenceFixture = createStressFixture()

function quote(value: string): string {
  return `"${value.replaceAll('\\', '\\\\').replaceAll('"', '\\"')}"`
}

function lowerCamelIdentifier(value: string, fallback: string): string {
  const parts = value.match(/[A-Za-z0-9]+/g) ?? []
  if (parts.length === 0) return fallback
  const first = parts[0] ?? fallback
  const rest = parts.slice(1)
  const identifier = [first.toLowerCase(), ...rest.map((part) => (
    part.charAt(0).toUpperCase() + part.slice(1)
  ))].join('')
  return /^[A-Za-z_$]/.test(identifier) ? identifier : `${fallback}${identifier}`
}

function callLabel(label: string, fallback: string): string {
  if (/^[A-Za-z_$][\w$]*\([^\n]*\)$/.test(label)) return label
  return `${lowerCamelIdentifier(label, fallback)}()`
}

function returnExpression(label: string, fallback: string): { renderedLabel: string; source: string } {
  if (/^[A-Za-z_$][\w$]*$/.test(label)) return { renderedLabel: label, source: label }
  if (label.trim().length > 0) return { renderedLabel: label, source: quote(label) }
  return { renderedLabel: fallback, source: fallback }
}

function intervalsCross(left: Interval, right: Interval): boolean {
  return (
    left.start < right.start
    && right.start <= left.end
    && left.end < right.end
  ) || (
    right.start < left.start
    && left.start <= right.end
    && right.end < left.end
  )
}

function validateIntervals(intervals: readonly Interval[]): void {
  for (let left = 0; left < intervals.length; left += 1) {
    for (let right = left + 1; right < intervals.length; right += 1) {
      if (intervalsCross(intervals[left], intervals[right])) {
        throw new Error(`Sequence intervals cross: ${intervals[left].id} and ${intervals[right].id}`)
      }
    }
  }
}

function findCallReturns(messages: readonly SequenceFixtureMessage[]): {
  callToReturn: ReadonlyMap<string, string>
  returnToCall: ReadonlyMap<string, string>
  intervals: readonly Interval[]
} {
  const callToReturn = new Map<string, string>()
  const returnToCall = new Map<string, string>()
  const usedReturns = new Set<string>()
  const intervals: Interval[] = []

  messages.forEach((message, callIndex) => {
    if (message.kind !== 'sync') return
    const returnIndex = messages.findIndex((candidate, candidateIndex) => (
      candidateIndex > callIndex
      && candidate.kind === 'return'
      && candidate.from === message.to
      && candidate.to === message.from
      && !usedReturns.has(candidate.id)
    ))
    if (returnIndex < 0) return
    const matchedReturn = messages[returnIndex]
    callToReturn.set(message.id, matchedReturn.id)
    returnToCall.set(matchedReturn.id, message.id)
    usedReturns.add(matchedReturn.id)
    intervals.push({ id: `${message.id}/${matchedReturn.id}`, start: callIndex, end: returnIndex })
  })

  validateIntervals(intervals)
  return { callToReturn, returnToCall, intervals }
}

export function compileZenUml(fixture: SequenceFixture): ZenUmlCompilation {
  if (fixture.participants.length === 0) throw new Error('A sequence requires at least one participant')

  const participantIds = new Set<string>()
  const participantIdsByAlias = new Map<string, string>()
  const aliasByParticipantId = new Map<string, string>()
  fixture.participants.forEach((participant, index) => {
    if (participantIds.has(participant.id)) throw new Error(`Duplicate participant ID: ${participant.id}`)
    participantIds.add(participant.id)
    const alias = `p${index + 1}`
    participantIdsByAlias.set(alias, participant.id)
    aliasByParticipantId.set(participant.id, alias)
  })

  const messageIndexById = new Map<string, number>()
  fixture.messages.forEach((message, index) => {
    if (messageIndexById.has(message.id)) throw new Error(`Duplicate message ID: ${message.id}`)
    if (!participantIds.has(message.from) || !participantIds.has(message.to)) {
      throw new Error(`Message ${message.id} references an unknown participant`)
    }
    messageIndexById.set(message.id, index)
  })

  const fragmentIntervals = fixture.fragments.map((fragment): Interval => {
    const start = messageIndexById.get(fragment.startMessageId)
    const end = messageIndexById.get(fragment.endMessageId)
    if (start === undefined || end === undefined || start > end) {
      throw new Error(`Fragment ${fragment.id} has invalid message bounds`)
    }
    return { id: fragment.id, start, end }
  })
  validateIntervals(fragmentIntervals)

  const { callToReturn, returnToCall, intervals: callIntervals } = findCallReturns(fixture.messages)
  validateIntervals([...fragmentIntervals, ...callIntervals])

  const fragmentsById = new Map(fixture.fragments.map((fragment) => [fragment.id, fragment]))
  const openingFragments = new Map<number, Interval[]>()
  const closingFragments = new Map<number, Interval[]>()
  fragmentIntervals.forEach((interval) => {
    openingFragments.set(interval.start, [...(openingFragments.get(interval.start) ?? []), interval])
    closingFragments.set(interval.end, [...(closingFragments.get(interval.end) ?? []), interval])
  })
  openingFragments.forEach((intervals) => intervals.sort((left, right) => right.end - left.end))
  closingFragments.forEach((intervals) => intervals.sort((left, right) => right.start - left.start))

  const lines = [
    `title ${fixture.title}`,
    '',
    ...fixture.participants.map((participant, index) => `p${index + 1} as ${quote(participant.label)}`),
    `@Starter(p1)`,
    '',
  ]
  const eventBindings: ZenUmlEventBinding[] = []
  let indent = 0
  const write = (line: string) => lines.push(`${'  '.repeat(indent)}${line}`)

  fixture.messages.forEach((message, index) => {
    for (const interval of openingFragments.get(index) ?? []) {
      const fragment = fragmentsById.get(interval.id)
      if (!fragment) throw new Error(`Missing fragment ${interval.id}`)
      const keyword = fragment.kind === 'alt' ? 'if' : 'loop'
      write(`${keyword} (${fragment.condition}) {`)
      indent += 1
    }

    const source = aliasByParticipantId.get(message.from)
    const target = aliasByParticipantId.get(message.to)
    if (!source || !target) throw new Error(`Message ${message.id} has unresolved participants`)

    if (message.kind === 'sync') {
      const renderedLabel = callLabel(message.label, `message${index + 1}`)
      const opensOccurrence = callToReturn.has(message.id)
      write(`${source} -> ${target}.${renderedLabel}${opensOccurrence ? ' {' : ''}`)
      if (opensOccurrence) indent += 1
      eventBindings.push({ id: message.id, renderedLabel, elementKind: 'message' })
    } else if (message.kind === 'async') {
      write(`${source} -> ${target}: ${message.label}`)
      eventBindings.push({ id: message.id, renderedLabel: message.label, elementKind: 'message' })
    } else if (returnToCall.has(message.id)) {
      const { renderedLabel, source: returnSource } = returnExpression(message.label, `result${index + 1}`)
      indent -= 1
      write(`return ${returnSource}`)
      write('}')
      eventBindings.push({ id: message.id, renderedLabel, elementKind: 'return' })
    } else {
      write(`${source} --> ${target}: ${message.label}`)
      eventBindings.push({ id: message.id, renderedLabel: message.label, elementKind: 'return' })
    }

    for (const _interval of closingFragments.get(index) ?? []) {
      indent -= 1
      write('}')
    }
  })

  if (indent !== 0) throw new Error(`Unbalanced generated ZenUML source: depth ${indent}`)
  return { source: lines.join('\n'), participantIdsByAlias, eventBindings }
}
