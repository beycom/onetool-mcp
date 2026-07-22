import { Button, Group, NavLink, Stack, Text, TextInput } from '@mantine/core'
import { useDeferredValue, useMemo } from 'react'

import type { BrowseGroup, ViewGraphNode } from '../data/types'
import { useExplorer } from './ExplorerProvider'
import { StatusMark } from './StatusMark'

interface BrowseItem {
  id: string
  label: string
  description?: string
  status?: ViewGraphNode['status']
}

function BrowseList({ items }: { items: BrowseItem[] }) {
  const { state, actions } = useExplorer()
  const deferredSearch = useDeferredValue(state.search)
  const filtered = useMemo(() => {
    const query = deferredSearch.trim().toLowerCase()
    if (!query) return items
    return items.filter((item) =>
      `${item.id} ${item.label} ${item.description ?? ''}`.toLowerCase().includes(query),
    )
  }, [deferredSearch, items])
  return (
    <Stack gap={2} mt="sm" opacity={state.search === deferredSearch ? 1 : 0.7}>
      {filtered.map((item) => (
        <NavLink
          active={state.subject === item.id}
          className="browse-item"
          description={item.description}
          key={item.id}
          label={
            <Group gap="xs" justify="space-between" wrap="nowrap">
              <Text fw={500} size="sm" truncate="end">
                {item.label}
              </Text>
              {item.status ? <StatusMark status={item.status} /> : null}
            </Group>
          }
          onClick={() => {
            actions.setSubject(item.id)
            actions.selectEntity(item.id)
          }}
        />
      ))}
      {filtered.length === 0 ? (
        <Text c="dimmed" p="md" size="sm">
          No matching items.
        </Text>
      ) : null}
    </Stack>
  )
}

export function SystemScreen() {
  const { meta, state } = useExplorer()
  const prepared = meta.prepared
  const snapshot = prepared?.snapshots[String(state.snapshotOrder)]
  const indexes = prepared?.indexes[String(state.snapshotOrder)]
  const items = useMemo<BrowseItem[]>(
    () => {
      const roadmapSystems = new Map(
        Object.values(prepared?.snapshots ?? {})
          .flatMap((graph) => graph.nodes)
          .filter((node) => node.entity_kind === 'system')
          .map((node) => [node.id, node]),
      )
      const snapshotSystems = new Map(
        (snapshot?.nodes ?? [])
          .filter((node) => node.entity_kind === 'system')
          .map((node) => [node.id, node]),
      )
      return (indexes?.systems ?? [...snapshotSystems.keys()]).flatMap((id) => {
        const node = snapshotSystems.get(id) ?? roadmapSystems.get(id)
        if (!node) return []
        const present = snapshotSystems.has(id)
        return [{
          id: node.id,
          label: node.name,
          description: present
            ? `${node.children.length} children · ${node.related_changes.length} changes`
            : 'Not present at this snapshot',
          status: present ? node.status : undefined,
        }]
      })
    },
    [indexes, prepared, snapshot],
  )
  return <BrowseList items={items} />
}

export function ChangeScreen() {
  const { meta, state } = useExplorer()
  const prepared = meta.prepared
  const snapshot = prepared?.snapshots[String(state.snapshotOrder)]
  const items = useMemo<BrowseItem[]>(
    () =>
      (snapshot?.changes ?? []).map((change) => ({
        id: change.id,
        label: change.name,
        description: `Order ${change.order} · ${change.affected_systems.join(', ') || 'No systems'}`,
      })),
    [snapshot],
  )
  return <BrowseList items={items} />
}

function IndexScreen({ kind }: { kind: 'system_groups' | 'change_groups' | 'tags' }) {
  const { meta, state } = useExplorer()
  const prepared = meta.prepared
  const indexes = prepared?.indexes[String(state.snapshotOrder)]
  const items = useMemo<BrowseItem[]>(
    () =>
      Object.entries(indexes?.[kind] ?? {}).map(([id, systems]) => ({
        id,
        label: id,
        description: `${systems.length} system${systems.length === 1 ? '' : 's'}`,
      })),
    [indexes, kind],
  )
  return <BrowseList items={items} />
}

export function ExplorerNavigation() {
  const { meta, state, actions } = useExplorer()
  const groups: { value: BrowseGroup; label: string }[] = [
    { value: 'system', label: 'Systems' },
    { value: 'system_group', label: 'System groups' },
    { value: 'change', label: 'Changes' },
    { value: 'change_group', label: 'Change groups' },
    { value: 'tag', label: 'Tags' },
  ]
  return (
    <>
      <Text fw={600} size="sm">
        Browse architecture
      </Text>
      <Group gap={4} mt="xs">
        {groups.map((group) => (
          <Button
            aria-pressed={state.browseBy === group.value}
            key={group.value}
            onClick={() => actions.setBrowseBy(group.value)}
            size="compact-xs"
            variant={state.browseBy === group.value ? 'filled' : 'subtle'}
          >
            {group.label}
          </Button>
        ))}
      </Group>
      <TextInput
        aria-label="Search navigation"
        mt="sm"
        onChange={(event) => actions.setSearch(event.currentTarget.value)}
        placeholder="Search this list"
        type="search"
        value={state.search}
      />
      {state.browseBy === 'system' ? <SystemScreen /> : null}
      {state.browseBy === 'system_group' ? <IndexScreen kind="system_groups" /> : null}
      {state.browseBy === 'change' ? <ChangeScreen /> : null}
      {state.browseBy === 'change_group' ? <IndexScreen kind="change_groups" /> : null}
      {state.browseBy === 'tag' ? <IndexScreen kind="tags" /> : null}
      {meta.solution && meta.solution.boundaryInterfaces.length > 0 ? (
        <Stack gap={2} mt="lg">
          <Text fw={600} size="xs">
            Boundary interfaces
          </Text>
          {meta.solution.boundaryInterfaces.map((boundary) => (
            <NavLink
              description={`${boundary.interface.source_id} → ${boundary.interface.target_id}`}
              key={boundary.interface.id}
              label={boundary.interface.name}
              onClick={() => actions.selectEntity(boundary.interface.id)}
            />
          ))}
        </Stack>
      ) : null}
      {meta.data.unavailableOrders.length > 0 ? (
        <Text c="dimmed" mt="md" size="xs">
          Unavailable orders: {meta.data.unavailableOrders.join(', ')}
        </Text>
      ) : null}
    </>
  )
}
