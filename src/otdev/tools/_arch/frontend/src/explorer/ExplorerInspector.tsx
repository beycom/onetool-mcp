import { Button, Code, Divider, Group, Stack, Text, Title } from '@mantine/core'

import type { ViewGraphEdge, ViewGraphNode } from '../data/types'
import { useExplorer } from './ExplorerProvider'
import { StatusMark } from './StatusMark'

function PropertyList({ properties }: { properties: Record<string, unknown> }) {
  const entries = Object.entries(properties)
  if (entries.length === 0)
    return (
      <Text c="dimmed" size="sm">
        None
      </Text>
    )
  return (
    <Stack gap={4}>
      {entries.map(([name, value]) => (
        <Group gap="xs" key={name} wrap="nowrap">
          <Text c="dimmed" fw={600} size="xs">
            {name}
          </Text>
          <Text size="xs">
            {typeof value === 'string' ? value : JSON.stringify(value)}
          </Text>
        </Group>
      ))}
    </Stack>
  )
}

function descendantIds(node: ViewGraphNode, nodes: ViewGraphNode[]): Set<string> {
  const result = new Set([node.id])
  let changed = true
  while (changed) {
    changed = false
    for (const candidate of nodes) {
      if (candidate.parent && result.has(candidate.parent) && !result.has(candidate.id)) {
        result.add(candidate.id)
        changed = true
      }
    }
  }
  return result
}

function RelationshipList({
  edges,
  onSelect,
}: {
  edges: ViewGraphEdge[]
  onSelect: (id: string) => void
}) {
  if (edges.length === 0)
    return (
      <Text c="dimmed" size="sm">
        None
      </Text>
    )
  return (
    <Stack gap={4}>
      {edges.map((edge) => (
        <Button
          fullWidth
          justify="space-between"
          key={edge.id}
          onClick={() => onSelect(edge.id)}
          size="compact-sm"
          variant="subtle"
        >
          <span>{edge.name}</span>
          <Code>{`${edge.source_id} → ${edge.target_id}`}</Code>
        </Button>
      ))}
    </Stack>
  )
}

export function ExplorerInspector() {
  const { state, actions, meta } = useExplorer()
  const selected = state.selectedId
    ? (meta.nodeById.get(state.selectedId) ?? meta.edgeById.get(state.selectedId))
    : undefined
  if (!selected) {
    return (
      <Text c="dimmed" size="sm">
        Select a system, element, or interface to inspect its stable identity and source.
      </Text>
    )
  }
  const isEdge = 'source_id' in selected
  const node = isEdge ? undefined : selected
  const endpointIds = node ? descendantIds(node, meta.graph.nodes) : new Set<string>()
  const allEdges = [
    ...meta.graph.edges,
    ...(meta.solution?.internalInterfaces ?? []),
    ...(meta.solution?.boundaryInterfaces.map((item) => item.interface) ?? []),
  ].filter((edge, index, edges) => edges.findIndex((candidate) => candidate.id === edge.id) === index)
  const relationships = node
    ? allEdges.filter(
        (edge) => endpointIds.has(edge.source_id) || endpointIds.has(edge.target_id),
      )
    : []
  const direct = relationships.filter(
    (edge) => edge.source_id === node?.id || edge.target_id === node?.id,
  )
  const nested = relationships.filter((edge) => !direct.includes(edge))
  const collapsed = isEdge
    ? meta.solution?.collapsedInterfaces.find((item) => item.interface.id === selected.id)
    : undefined
  const visibleEdge = isEdge
    ? meta.graph.edges.find(
        (edge) => edge.id === selected.id || edge.interface_ids.includes(selected.id),
      )
    : undefined
  const contributingIds = isEdge
    ? selected.interface_ids.length > 0
      ? selected.interface_ids
      : [selected.id]
    : []
  return (
    <Stack gap="sm">
      <Group justify="space-between" wrap="nowrap">
        <Title order={2} size="h4">
          {selected.name}
        </Title>
        <Button onClick={() => actions.selectEntity()} size="compact-xs" variant="subtle">
          Close
        </Button>
      </Group>
      <Group gap="xs">
        <StatusMark status={selected.status} />
        <Code>{selected.id}</Code>
      </Group>
      {isEdge ? (
        <Stack gap={2}>
          <Text size="sm">
            Canonical endpoints: {selected.source_id} → {selected.target_id}
          </Text>
          {visibleEdge &&
          (visibleEdge.source_id !== selected.source_id ||
            visibleEdge.target_id !== selected.target_id) ? (
            <Text size="sm">
              Visible endpoints: {visibleEdge.source_id} → {visibleEdge.target_id}
            </Text>
          ) : null}
          <Text size="xs">Direction: {selected.direction}</Text>
          <Text size="xs">Kind: {selected.entity_kind}</Text>
        </Stack>
      ) : (
        <Text size="sm">{selected.entity_kind}</Text>
      )}
      <Divider />
      <Text fw={600} size="sm">
        Related changes
      </Text>
      <Text c="dimmed" size="sm">
        {selected.related_changes.join(', ') || 'None'}
      </Text>
      {(!isEdge ? selected.groups.length > 0 : false) || selected.tags.length > 0 ? (
        <Text c="dimmed" size="xs">
          {[
            ...(!isEdge ? selected.groups.map((group) => `Group: ${group}`) : []),
            ...selected.tags.map((tag) => `Tag: ${tag}`),
          ].join(' · ')}
        </Text>
      ) : null}
      {isEdge && selected.integration_type ? (
        <Text size="sm">Integration type: {selected.integration_type}</Text>
      ) : null}
      {isEdge && selected.description ? (
        <Text size="sm">{selected.description}</Text>
      ) : null}
      {isEdge && contributingIds.length > 0 ? (
        <>
          <Text fw={600} size="sm">Contributing interfaces</Text>
          <Text c="dimmed" size="xs">{contributingIds.join(', ')}</Text>
        </>
      ) : null}
      {collapsed ? (
        <Text c="orange" size="sm">
          This interface is not drawn because it collapsed within visible node{' '}
          <Button
            onClick={() => actions.selectEntity(collapsed.visible_node)}
            size="compact-xs"
            variant="subtle"
          >
            {collapsed.visible_node}
          </Button>
        </Text>
      ) : null}
      <Text fw={600} size="sm">
        Properties
      </Text>
      <PropertyList properties={selected.properties} />
      {node ? (
        <>
          <Text fw={600} size="sm">
            Relationships
          </Text>
          {direct.length > 0 ? (
            <>
              <Text c="dimmed" fw={600} size="xs">
                Direct
              </Text>
              <RelationshipList edges={direct} onSelect={actions.selectEntity} />
            </>
          ) : null}
          {nested.length > 0 ? (
            <>
              <Text c="dimmed" fw={600} size="xs">
                Resolved from nested elements
              </Text>
              <RelationshipList edges={nested} onSelect={actions.selectEntity} />
            </>
          ) : null}
          {relationships.length === 0 ? (
            <Text c="dimmed" size="sm">
              None
            </Text>
          ) : null}
        </>
      ) : null}
      <Text fw={600} size="sm">
        Source
      </Text>
      <Text c="dimmed" size="xs">
        {selected.source
          ? [
              selected.source.path,
              selected.source.yaml_path,
              selected.source.sheet,
              selected.source.row,
              selected.source.column,
            ]
              .filter(Boolean)
              .join(' · ')
          : 'Generated source'}
      </Text>
    </Stack>
  )
}
