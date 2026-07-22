import { Badge, Group, Paper, Stack, Text } from '@mantine/core'
import { useMemo } from 'react'

import { useExplorer } from '../explorer/ExplorerProvider'

const SELECTOR_LABELS = {
  systems: 'Systems',
  system_groups: 'System groups',
  changes: 'Changes',
  change_groups: 'Change groups',
  tags: 'Tags',
} as const

export function SolutionSummary() {
  const { state, meta } = useExplorer()
  const solution = meta.solution
  const names = useMemo(() => {
    const result = new Map<string, string>()
    for (const graph of Object.values(meta.prepared?.snapshots ?? {})) {
      for (const node of graph.nodes) {
        if (node.entity_kind === 'system') result.set(node.id, node.name)
      }
    }
    return result
  }, [meta.prepared])
  if (!solution) return null
  const selectorEntries = Object.entries(solution.graph.selection.selection.system_set).filter(
    ([, values]) => values.length > 0,
  ) as [keyof typeof SELECTOR_LABELS, string[]][]
  const expanded = Object.entries(solution.systemDistances)
    .filter(([, distance]) => distance > 0)
    .sort((left, right) => left[1] - right[1] || left[0].localeCompare(right[0]))
  return (
    <Paper aria-label="Active solution summary" className="solution-summary" p="sm" shadow="sm">
      <Stack gap={4}>
        <Group gap="xs">
          <Text fw={700} size="sm">Active solution</Text>
          <Badge variant="light">Order {state.snapshotOrder}</Badge>
          <Badge variant="light">{state.level.toUpperCase()}</Badge>
          <Badge variant="light">Depth {state.interfaceDepth}</Badge>
          <Badge variant="light">{state.colorBy.replaceAll('_', ' ')}</Badge>
        </Group>
        <Text size="xs">
          Scope: {selectorEntries.length > 0
            ? selectorEntries
                .map(([kind, values]) => `${SELECTOR_LABELS[kind]} - ${values.join(', ')}`)
                .join(' · ')
            : 'All roadmap systems'}
        </Text>
        <Text size="xs">
          Seeds: {solution.selectedSystems.map((id) => names.get(id) ?? id).join(', ') || 'None'}
        </Text>
        {expanded.length > 0 ? (
          <Text size="xs">
            Expanded: {expanded
              .map(([id, distance]) => `${names.get(id) ?? id} (${distance})`)
              .join(', ')}
          </Text>
        ) : null}
        {solution.absentSystems.length > 0 ? (
          <Text c="orange" size="xs">
            Absent: {solution.absentSystems
              .map((item) => `${names.get(item.system_id) ?? item.system_id} - ${item.message}`)
              .join(', ')}
          </Text>
        ) : null}
      </Stack>
    </Paper>
  )
}
