import { expect, test } from 'vitest'

import { cardSize } from './cardSize'
import type { GraphNode } from './types'

function node(name: string): GraphNode {
  return {
    key: `systems:${name}`,
    kind: 'systems',
    row: { id: name, name, intervals: [] },
    boundary: false,
    members: [],
  }
}

test('a long name uses two full lines and grows the card before truncating', () => {
  const measure = (text: string) => text.length * 8
  const short = cardSize(node('Checkout'), 'systems', measure)
  const long = cardSize(node('Enterprise commerce and fulfilment coordination platform'), 'systems', measure)

  expect(short.nameLines).toBe(1)
  expect(long.nameLines).toBe(2)
  expect(long.height).toBe(short.height + 18)
})
