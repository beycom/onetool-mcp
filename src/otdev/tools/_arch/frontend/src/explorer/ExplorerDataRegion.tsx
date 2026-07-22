import { Tabs } from '@mantine/core'
import { lazy, Suspense, useMemo } from 'react'

import type { SourceLocation, ViewGraphEdge } from '../data/types'
import type { ArchitectureRow } from '../grid/ArchitectureGrid'
import { useExplorer } from './ExplorerProvider'

const ArchitectureGrid = lazy(() =>
  import('../grid/ArchitectureGrid').then((module) => ({ default: module.ArchitectureGrid })),
)

function sourceTrace(source?: SourceLocation): string {
  if (!source) return 'Generated source'
  return [source.path, source.yaml_path, source.sheet, source.row, source.column]
    .filter((value) => value !== undefined)
    .join(' · ')
}

function interfaceRow(edge: ViewGraphEdge): ArchitectureRow {
  return {
    id: edge.id,
    name: edge.name,
    kind: edge.entity_kind,
    status: edge.status,
    source: edge.source_id,
    target: edge.target_id,
    provider: edge.source_id,
    consumer: edge.target_id,
    direction: edge.direction,
    integration_type: edge.integration_type,
    description: edge.description,
    tags: edge.tags.join('; '),
    properties: JSON.stringify(edge.properties),
    source_trace: sourceTrace(edge.source),
    interface_ids: edge.interface_ids.join('; '),
    related_changes: edge.related_changes.join('; '),
  }
}

export function ExplorerDataRegion() {
  const { state, actions, meta } = useExplorer()
  const elementRows = useMemo<ArchitectureRow[]>(
    () =>
      meta.graph.nodes.map((node) => ({
        id: node.id,
        name: node.name,
        kind: node.entity_kind,
        status: node.status,
        parent: node.parent,
        tags: node.tags.join('; '),
        groups: node.groups.join('; '),
        properties: JSON.stringify(node.properties),
        source_trace: sourceTrace(node.source),
        related_changes: node.related_changes.join('; '),
      })),
    [meta.graph.nodes],
  )
  const includedRows = useMemo(
    () => (meta.solution?.internalInterfaces ?? []).map(interfaceRow),
    [meta.solution?.internalInterfaces],
  )
  const boundaryRows = useMemo(
    () =>
      (meta.solution?.boundaryInterfaces ?? []).map((boundary) => ({
        ...interfaceRow(boundary.interface),
        inside_system: boundary.inside_system,
        inside_endpoint: boundary.inside_endpoint,
        outside_system: boundary.outside_system,
        outside_endpoint: boundary.outside_endpoint,
      })),
    [meta.solution?.boundaryInterfaces],
  )
  const selectedEdge = state.selectedId ? meta.edgeById.get(state.selectedId) : undefined
  const selectedInterfaceIds = selectedEdge?.interface_ids.length
    ? selectedEdge.interface_ids
    : state.selectedId
      ? [state.selectedId]
      : []
  const selectInterface = (id?: string) => {
    if (!id) return actions.selectEntity()
    actions.selectEntity(id)
  }
  const grids = {
    elements: {
      label: 'Elements',
      rows: elementRows,
      selectedIds: state.selectedId && meta.nodeById.has(state.selectedId) ? [state.selectedId] : [],
      onSelect: actions.selectEntity,
    },
    included_interfaces: {
      label: 'Included interfaces',
      rows: includedRows,
      selectedIds: selectedInterfaceIds,
      onSelect: selectInterface,
    },
    boundary_interfaces: {
      label: 'Boundary interfaces',
      rows: boundaryRows,
      selectedIds: selectedInterfaceIds,
      onSelect: selectInterface,
    },
  } as const
  const active = grids[state.activeTable]
  const config = meta.data.tableConfigs.find((table) => table.id === state.activeTable)
  return (
    <Tabs
      onChange={(value) =>
        value && actions.setActiveTable(value as keyof typeof grids)
      }
      value={state.activeTable}
    >
      <Tabs.List>
        <Tabs.Tab value="elements">Elements ({elementRows.length})</Tabs.Tab>
        <Tabs.Tab value="included_interfaces">Included interfaces ({includedRows.length})</Tabs.Tab>
        <Tabs.Tab value="boundary_interfaces">Boundary interfaces ({boundaryRows.length})</Tabs.Tab>
      </Tabs.List>
      <Suspense fallback={<p aria-live="polite">Loading architecture table…</p>}>
        <ArchitectureGrid
          config={config}
          density={state.preferences.density}
          label={active.label}
          onDensityChange={actions.setDensity}
          onDiagnostic={actions.reportDiagnostic}
          onLayoutChange={(layout) => actions.setTableLayout(state.activeTable, layout)}
          onSelect={active.onSelect}
          rememberedLayout={state.preferences.tableLayouts[state.activeTable]}
          rows={active.rows}
          selectedIds={[...active.selectedIds]}
          tableId={state.activeTable}
        />
      </Suspense>
    </Tabs>
  )
}
