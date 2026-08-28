import type { GraphNode, Level } from './types'

export type TextMeasure = (text: string, font: string) => number
export type CardDimensions = { width: number; height: number; nameLines: 1 | 2 }

export const CARD_WIDTH: Record<Level, number> = {
  systems: 280,
  'top-containers': 260,
  containers: 240,
  components: 240,
}

const NAME_FONT = '600 14px Inter, ui-sans-serif, sans-serif'
const BODY_FONT = '10px Inter, ui-sans-serif, sans-serif'
const HORIZONTAL_PADDING = 28
const NAME_LINE_HEIGHT = 18
const BODY_LINE_HEIGHT = 13
const ROW_GAP = 5
const VERTICAL_PADDING = 22

let measuringContext: CanvasRenderingContext2D | null | undefined

export function measureCardText(text: string, font: string): number {
  if (measuringContext === undefined) {
    const canvas = globalThis.document?.createElement('canvas')
    measuringContext = canvas?.getContext('2d') ?? null
  }
  if (!measuringContext) return text.length * 8
  measuringContext.font = font
  return measuringContext.measureText(text).width
}

function wrappedLines(text: string, width: number, font: string, measure: TextMeasure): number {
  if (!text) return 0
  return Math.max(1, Math.ceil(measure(text, font) / width))
}

export function cardSize(node: GraphNode, level: Level, measure: TextMeasure): CardDimensions {
  const width = CARD_WIDTH[level]
  const textWidth = width - HORIZONTAL_PADDING
  const name = node.row.name ?? node.row.action ?? node.row.id
  const nameLines = Math.min(2, wrappedLines(name, textWidth, NAME_FONT, measure)) as 1 | 2
  if (node.boundary) {
    return {
      width,
      height: VERTICAL_PADDING + 18 + nameLines * NAME_LINE_HEIGHT + 18 + ROW_GAP * 2,
      nameLines,
    }
  }
  const descriptionLines = Math.min(2, wrappedLines(node.row.description ?? '', textWidth, BODY_FONT, measure))
  const hasFacts = Object.keys(node.row.properties ?? {}).length > 0
  const rowHeights = [
    18,
    nameLines * NAME_LINE_HEIGHT,
    ...(descriptionLines ? [descriptionLines * BODY_LINE_HEIGHT] : []),
    13,
    ...(hasFacts ? [20] : []),
    20,
  ]
  return {
    width,
    height: VERTICAL_PADDING + rowHeights.reduce((total, value) => total + value, 0) + (rowHeights.length - 1) * ROW_GAP,
    nameLines,
  }
}
