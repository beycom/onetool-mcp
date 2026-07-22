import { Alert, Button, Modal, Stack, Text } from '@mantine/core'
import { useMemo, useState } from 'react'

import type { ColorBy, PresentationConfig, ViewGraph } from '../data/types'
import { ExplorerInspector } from '../explorer/ExplorerInspector'
import { solutionColors } from './colors'
import { LikeC4SolutionRenderer } from './renderer/LikeC4SolutionRenderer'
import type { SolutionLayoutResult } from './renderer/types'
import {
  DEFAULT_PROJECTION_THRESHOLDS,
  projectionSizeState,
  type ProjectionThresholds,
} from './runtime'

export function DynamicSolutionDiagram({
  cacheKey,
  colorBy,
  graph,
  onLayout,
  onReduceDepth,
  onSelect,
  pending = false,
  presentation,
  selectionFocusId,
  selectedId,
  thresholds = DEFAULT_PROJECTION_THRESHOLDS,
}: {
  cacheKey: string
  colorBy: ColorBy
  graph: ViewGraph
  onLayout: (layout: SolutionLayoutResult) => void
  onReduceDepth: () => void
  onSelect: (id: string) => void
  pending?: boolean
  presentation: PresentationConfig
  selectionFocusId?: string
  selectedId?: string
  thresholds?: ProjectionThresholds
}) {
  const [fullExplorerOpen, setFullExplorerOpen] = useState(false)
  const { nodeColors, edgeColors } = useMemo(
    () => solutionColors(graph, colorBy, presentation),
    [colorBy, graph, presentation],
  )
  const rendererSelectedId = selectionFocusId ?? (selectedId
    ? (graph.edges.find(
        (edge) => edge.id === selectedId || edge.interface_ids.includes(selectedId),
      )?.id ?? selectedId)
    : undefined)
  const sizeState = projectionSizeState(graph, thresholds)
  const selector = graph.selection.selection.system_set
  const selectorValues = Object.values(selector).flat()
  const selectorLabel = selectorValues.length > 0 ? selectorValues.join(', ') : 'all systems'
  const renderer = (controls: boolean) => (
    <LikeC4SolutionRenderer
      cacheKey={cacheKey}
      controls={controls}
      edgeColors={edgeColors}
      graph={graph}
      nodeColors={nodeColors}
      onCanvasClick={controls ? undefined : () => setFullExplorerOpen(true)}
      onLayout={onLayout}
      onSelect={(event) => onSelect(event.id)}
      selectedId={rendererSelectedId}
    />
  )
  return (
    <>
      <Stack gap="xs" h="100%">
        {pending ? (
          <Alert color="blue" title="Updating solution">
            Applying the latest selector and layout request.
          </Alert>
        ) : null}
        {graph.nodes.length === 0 ? (
          <Alert color="blue" title="No elements match this solution">
            Selector {selectorLabel} has no elements at this snapshot.
          </Alert>
        ) : sizeState === 'hard' ? (
          <Alert color="red" title="Solution is too large to lay out safely">
            <Text size="sm">
              Selector {selectorLabel} at depth {graph.selection.selection.interface_depth} produced{' '}
              {graph.nodes.length} nodes and {graph.edges.length} edges.
            </Text>
            <Button mt="xs" onClick={onReduceDepth} size="compact-sm" variant="light">
              Reduce interface depth
            </Button>
          </Alert>
        ) : (
          <>
            {sizeState === 'warning' ? (
              <Alert color="yellow" title="Large solution projection">
                Selector {selectorLabel} at depth {graph.selection.selection.interface_depth} produced{' '}
                {graph.nodes.length} nodes and {graph.edges.length} edges. Interaction may be slower.
              </Alert>
            ) : null}
            {renderer(false)}
          </>
        )}
      </Stack>
      <Button
        className="open-full-explorer"
        onClick={() => setFullExplorerOpen(true)}
        size="compact-sm"
        variant="default"
      >
        Open full explorer
      </Button>
      <Modal
        fullScreen
        onClose={() => setFullExplorerOpen(false)}
        opened={fullExplorerOpen}
        title="Full solution explorer"
      >
        <div className="full-explorer-layout">
          <div className="full-explorer-canvas">
            {graph.nodes.length > 0 && sizeState !== 'hard' ? renderer(true) : null}
          </div>
          <aside aria-label="Full explorer details" className="full-explorer-details">
            <ExplorerInspector />
          </aside>
        </div>
      </Modal>
    </>
  )
}
