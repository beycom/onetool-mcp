export const MAX_SOLUTION_HISTORY = 100

export function initialDiagramId(fragmentDiagram?: string, savedDiagram?: string): string | undefined {
  return fragmentDiagram ?? savedDiagram
}

export function withDiagram<T extends { diagramId?: string }>(state: T, diagramId?: string): T {
  return { ...state, diagramId }
}

export function appendBoundedHistory<T>(
  history: T[],
  index: number,
  entry: T,
  limit = MAX_SOLUTION_HISTORY,
): { history: T[]; index: number } {
  if (limit < 1) throw new Error('History limit must be positive')
  if (JSON.stringify(entry) === JSON.stringify(history[index])) return { history, index }
  const next = [...history.slice(0, index + 1), entry].slice(-limit)
  return { history: next, index: next.length - 1 }
}
