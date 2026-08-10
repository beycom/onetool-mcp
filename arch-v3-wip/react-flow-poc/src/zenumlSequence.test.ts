import { parse } from '@zenuml/core/parser'
import { describe, expect, it } from 'vitest'

import {
  checkoutSequenceFixture,
  compileZenUml,
  stressSequenceFixture,
  type SequenceFixture,
} from './zenumlSequence'

describe('compileZenUml', () => {
  it('produces deterministic aliases and valid checkout syntax', () => {
    const first = compileZenUml(checkoutSequenceFixture)
    const second = compileZenUml(checkoutSequenceFixture)
    const parsed = parse(first.source)

    expect(first.source).toBe(second.source)
    expect(parsed.pass, parsed.errorDetails.map((error) => error.msg).join('\n')).toBe(true)
    expect([...first.participantIdsByAlias.entries()]).toEqual([
      ['p1', 'buyers'],
      ['p2', 'edge-gateway'],
      ['p3', 'checkout-api'],
      ['p4', 'session-cache'],
      ['p5', 'orders'],
      ['p6', 'payment-rail'],
    ])
    expect(first.eventBindings.map((binding) => binding.id)).toEqual(
      checkoutSequenceFixture.messages.map((message) => message.id),
    )
    expect(first.source).not.toContain('participant p1')
    expect(first.source).toContain('p1 as "Buyers"')
    expect(first.source).toContain('if (paymentApproved) {')
    expect(first.source).toContain('return approved')
    expect(first.source).toContain('return "202 Accepted"')
  })

  it('covers the bounded 12 participant / 100 message stress case', () => {
    const compilation = compileZenUml(stressSequenceFixture)
    const parsed = parse(compilation.source)

    expect(stressSequenceFixture.participants).toHaveLength(12)
    expect(stressSequenceFixture.messages).toHaveLength(100)
    expect(compilation.eventBindings).toHaveLength(100)
    expect(compilation.eventBindings.filter((binding) => binding.elementKind === 'return')).toHaveLength(50)
    expect(compilation.source).toContain('if (primaryPath) {')
    expect(compilation.source).toContain('loop (retryBudgetRemaining) {')
    expect(parsed.pass, parsed.errorDetails.map((error) => error.msg).join('\n')).toBe(true)
  })

  it('rejects crossing fragments rather than emitting ambiguous nesting', () => {
    const invalid: SequenceFixture = {
      ...checkoutSequenceFixture,
      fragments: [
        { id: 'left', kind: 'alt', condition: 'left', startMessageId: 'm2', endMessageId: 'm5' },
        { id: 'right', kind: 'loop', condition: 'right', startMessageId: 'm4', endMessageId: 'm7' },
      ],
    }

    expect(() => compileZenUml(invalid)).toThrow('Sequence intervals cross: left and right')
  })
})
