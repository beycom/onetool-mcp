import {
  createContext,
  use,
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

import type {
  BrowseGroup,
  ArchitectureLevel,
  ColorBy,
  Density,
  DiagramCatalogItem,
  ExplorerData,
  PreparedSolutionSnapshots,
  SolutionSelectionIndexes,
  SystemSetSelector,
  ViewGraph,
  ViewGraphEdge,
  ViewGraphNode,
} from '../data/types'
import { projectSolution, type LocalSolutionProjection } from '../solution/projection'
import {
  normalizedSelection,
  solutionSelectionIdentity,
  stableJson,
} from '../solution/identity'
import type { SolutionLayoutResult } from '../solution/renderer/types'
import { parseFragment, serializeFragment } from './fragment'
import {
  DEFAULT_PREFERENCES,
  loadPreferences,
  PREFERENCES_KEY,
  savePreferences,
  type ExplorerPreferences,
} from './preferences'
import { appendBoundedHistory, initialDiagramId, withDiagram } from './state'

export interface ExplorerState {
  graphId: string
  browseBy: BrowseGroup
  subject?: string
  systemSet: SystemSetSelector
  search: string
  snapshotOrder: number
  interfaceDepth: number
  level: ArchitectureLevel
  colorBy: ColorBy
  diagramId?: string
  selectedId?: string
  dataOpen: boolean
  inspectorOpen: boolean
  activeTable: 'elements' | 'included_interfaces' | 'boundary_interfaces'
  preferences: ExplorerPreferences
  diagnostics: string[]
}

export interface ExplorerActions {
  setGraph: (graphId: string) => void
  setBrowseBy: (browseBy: BrowseGroup) => void
  setSubject: (subject?: string) => void
  setSearch: (search: string) => void
  setSnapshotOrder: (order: number) => void
  setInterfaceDepth: (depth: number) => void
  setLevel: (level: ArchitectureLevel) => void
  setColorBy: (colorBy: ColorBy) => void
  setDiagram: (diagramId?: string) => void
  selectEntity: (id?: string) => void
  setDataOpen: (open: boolean) => void
  setInspectorOpen: (open: boolean) => void
  setActiveTable: (table: ExplorerState['activeTable']) => void
  setDensity: (density: Density) => void
  setColorScheme: (colorScheme: ExplorerPreferences['colorScheme']) => void
  setTableLayout: (tableId: string, layout: unknown[]) => void
  reportDiagnostic: (diagnostic: string) => void
  resetPreferences: () => void
  setActiveLayout: (layout: SolutionLayoutResult) => void
  goBack: () => void
  goForward: () => void
}

export interface ExplorerMeta {
  data: ExplorerData
  graph: ViewGraph
  nodeById: Map<string, ViewGraphNode>
  edgeById: Map<string, ViewGraphEdge>
  likec4ViewId: string
  canonicalByLikec4Id: Map<string, string>
  interfaceByLikec4EdgeId: Map<string, string[]>
  diagramCatalog: DiagramCatalogItem[]
  selectedDiagram?: DiagramCatalogItem
  hoveredId: React.RefObject<string | null>
  solution?: LocalSolutionProjection
  prepared?: PreparedSolutionSnapshots
  activeLayout?: SolutionLayoutResult
  solutionPending: boolean
  solutionIdentityPending: boolean
  canGoBack: boolean
  canGoForward: boolean
}

export interface ExplorerContextValue {
  state: ExplorerState
  actions: ExplorerActions
  meta: ExplorerMeta
}

const ExplorerContext = createContext<ExplorerContextValue | null>(null)

export function useExplorer(): ExplorerContextValue {
  const value = use(ExplorerContext)
  if (value === null) throw new Error('ExplorerProvider was not found in the tree')
  return value
}

interface ExplorerProviderProps {
  data: ExplorerData
  children: React.ReactNode
}

function initialPreferences(): ExplorerPreferences {
  return typeof window === 'undefined' ? DEFAULT_PREFERENCES : loadPreferences(window.localStorage)
}

function emptySystemSet(): SystemSetSelector {
  return { systems: [], system_groups: [], changes: [], change_groups: [], tags: [] }
}

function selectorFor(browseBy: BrowseGroup, subject?: string): SystemSetSelector {
  const selector = emptySystemSet()
  if (!subject) return selector
  const field = {
    system: 'systems',
    system_group: 'system_groups',
    change: 'changes',
    change_group: 'change_groups',
    tag: 'tags',
  }[browseBy] as keyof SystemSetSelector
  selector[field] = [subject]
  return selector
}

function selectorContext(
  selector: SystemSetSelector,
  fallback: BrowseGroup,
): { browseBy: BrowseGroup; subject?: string } {
  const entries: [BrowseGroup, string][] = [
    ...selector.systems.map((id): [BrowseGroup, string] => ['system', id]),
    ...selector.system_groups.map((id): [BrowseGroup, string] => ['system_group', id]),
    ...selector.changes.map((id): [BrowseGroup, string] => ['change', id]),
    ...selector.change_groups.map((id): [BrowseGroup, string] => ['change_group', id]),
    ...selector.tags.map((id): [BrowseGroup, string] => ['tag', id]),
  ]
  return entries.length === 1
    ? { browseBy: entries[0]![0], subject: entries[0]![1] }
    : { browseBy: fallback }
}

export function sanitizeSystemSet(
  selector: SystemSetSelector,
  indexes: SolutionSelectionIndexes,
): SystemSetSelector {
  const known = {
    systems: new Set(indexes.systems),
    system_groups: new Set(Object.keys(indexes.system_groups)),
    changes: new Set(Object.keys(indexes.changes)),
    change_groups: new Set(Object.keys(indexes.change_groups)),
    tags: new Set(Object.keys(indexes.tags)),
  }
  return {
    systems: selector.systems.filter((id) => known.systems.has(id)),
    system_groups: selector.system_groups.filter((id) => known.system_groups.has(id)),
    changes: selector.changes.filter((id) => known.changes.has(id)),
    change_groups: selector.change_groups.filter((id) => known.change_groups.has(id)),
    tags: selector.tags.filter((id) => known.tags.has(id)),
  }
}

type SolutionHistoryEntry = Pick<
  ExplorerState,
  | 'graphId'
  | 'browseBy'
  | 'subject'
  | 'systemSet'
  | 'snapshotOrder'
  | 'interfaceDepth'
  | 'level'
  | 'colorBy'
>

function historyEntry(state: ExplorerState): SolutionHistoryEntry {
  return {
    graphId: state.graphId,
    browseBy: state.browseBy,
    subject: state.subject,
    systemSet: state.systemSet,
    snapshotOrder: state.snapshotOrder,
    interfaceDepth: state.interfaceDepth,
    level: state.level,
    colorBy: state.colorBy,
  }
}

export function ExplorerProvider({ data, children }: ExplorerProviderProps) {
  const fragment = typeof window === 'undefined' ? {} : parseFragment(window.location.hash)
  const initialGraphId = data.graphs.some((graph) => graph.id === fragment.graph)
    ? fragment.graph!
    : data.initialGraphId
  const initialGraph = data.graphs.find((graph) => graph.id === initialGraphId) ?? data.graphs[0]!
  const initialSourceSelection = initialGraph.selection.selection
  const fallbackBrowse = initialSourceSelection.browse_by ?? 'system'
  const initialRoadmapId =
    initialGraph.selection.roadmap_id ??
    data.presentation.default_roadmap ??
    Object.keys(data.solutionSnapshots)[0]
  const initialPrepared = initialRoadmapId
    ? data.solutionSnapshots[initialRoadmapId]
    : undefined
  const fallbackOrder = initialGraph.selection.order ?? 0
  const initialOrder =
    fragment.order !== undefined && initialPrepared?.snapshots[String(fragment.order)]
      ? fragment.order
      : fallbackOrder
  const initialIndexes = initialPrepared?.indexes[String(initialOrder)]
  const fragmentSelector = fragment.subject
    ? selectorFor(fragment.browse ?? fallbackBrowse, fragment.subject)
    : undefined
  const requestedSystemSet =
    fragment.systemSet ?? fragmentSelector ?? initialSourceSelection.system_set
  const initialSystemSet = initialIndexes
    ? sanitizeSystemSet(requestedSystemSet, initialIndexes)
    : initialSourceSelection.system_set
  const initialContext = selectorContext(initialSystemSet, fragment.browse ?? fallbackBrowse)
  const [state, setState] = useState<ExplorerState>(() => ({
    graphId: initialGraphId,
    browseBy: initialContext.browseBy,
    subject: initialContext.subject,
    systemSet: initialSystemSet,
    search: fragment.search ?? '',
    snapshotOrder: initialOrder,
    interfaceDepth: fragment.depth ?? initialSourceSelection.interface_depth,
    level: fragment.level ?? initialSourceSelection.level,
    colorBy: fragment.colorBy ?? initialSourceSelection.color_by,
    diagramId: initialDiagramId(fragment.diagram, initialSourceSelection.diagram),
    selectedId: fragment.selected,
    dataOpen: fragment.dataOpen ?? false,
    inspectorOpen: fragment.inspectorOpen ?? Boolean(fragment.selected),
    activeTable: fragment.activeTable ?? 'elements',
    preferences: initialPreferences(),
    diagnostics: [...data.diagnostics],
  }))
  const solutionHistory = useRef<SolutionHistoryEntry[]>([])
  const solutionHistoryIndex = useRef(0)
  const [historyVersion, setHistoryVersion] = useState(0)
  const [activeLayout, setActiveLayout] = useState<SolutionLayoutResult>()
  if (solutionHistory.current.length === 0) solutionHistory.current = [historyEntry(state)]
  const hoveredId = useRef<string | null>(null)
  const graphById = useMemo(() => new Map(data.graphs.map((graph) => [graph.id, graph])), [data])
  const sourceGraph = graphById.get(state.graphId) ?? data.graphs[0]!
  const sourceSelection = sourceGraph.selection.selection
  const roadmapId =
    sourceGraph.selection.roadmap_id ??
    data.presentation.default_roadmap ??
    Object.keys(data.solutionSnapshots)[0]
  const prepared = roadmapId ? data.solutionSnapshots[roadmapId] : undefined
  const topologyRequest = useMemo(
    () => ({
      snapshotOrder: state.snapshotOrder,
      systemSet: state.systemSet,
      browseBy: state.browseBy,
      subject: state.subject,
      interfaceDepth: state.interfaceDepth,
      level: state.level,
    }),
    [
      state.browseBy,
      state.interfaceDepth,
      state.level,
      state.snapshotOrder,
      state.subject,
      state.systemSet,
    ],
  )
  const deferredTopologyRequest = useDeferredValue(topologyRequest)
  const topologySolution = useMemo(
    () =>
      prepared
        ? projectSolution(
            prepared,
            deferredTopologyRequest.snapshotOrder,
            deferredTopologyRequest.systemSet,
            deferredTopologyRequest.interfaceDepth,
            deferredTopologyRequest.level,
            sourceSelection.theme,
          )
        : undefined,
    [
      deferredTopologyRequest,
      prepared,
      sourceSelection.theme,
    ],
  )
  const activeSelection = useMemo(
    () =>
      topologySolution
        ? normalizedSelection({
            ...sourceSelection,
            state: undefined,
            roadmap: prepared?.roadmap_id,
            through: undefined,
            order: deferredTopologyRequest.snapshotOrder,
            browse_by: deferredTopologyRequest.browseBy,
            subject: deferredTopologyRequest.subject,
            system_set: topologySolution.graph.selection.selection.system_set,
            interface_depth: deferredTopologyRequest.interfaceDepth,
            level: deferredTopologyRequest.level,
            color_by: state.colorBy,
          })
        : undefined,
    [
      deferredTopologyRequest.interfaceDepth,
      deferredTopologyRequest.level,
      deferredTopologyRequest.snapshotOrder,
      deferredTopologyRequest.browseBy,
      deferredTopologyRequest.subject,
      prepared?.roadmap_id,
      sourceSelection,
      state.colorBy,
      topologySolution,
    ],
  )
  const activeSelectionKey = useMemo(
    () => (activeSelection ? stableJson(activeSelection) : undefined),
    [activeSelection],
  )
  const [activeSelectionIdentity, setActiveSelectionIdentity] = useState<{
    key: string
    id: string
  }>()
  useEffect(() => {
    if (!activeSelection || !activeSelectionKey) {
      setActiveSelectionIdentity(undefined)
      return
    }
    let cancelled = false
    void solutionSelectionIdentity(activeSelection).then((id) => {
      if (!cancelled) setActiveSelectionIdentity({ key: activeSelectionKey, id })
    })
    return () => {
      cancelled = true
    }
  }, [activeSelection, activeSelectionKey])
  const solutionIdentityPending =
    topologySolution !== undefined && activeSelectionIdentity?.key !== activeSelectionKey
  const resolvedActiveSelectionId =
    activeSelectionIdentity && activeSelectionIdentity.key === activeSelectionKey
      ? activeSelectionIdentity.id
      : undefined
  const solution = useMemo(
    () =>
      topologySolution && activeSelection
        ? {
            ...topologySolution,
            graph: {
              ...topologySolution.graph,
              id: resolvedActiveSelectionId
                ? `solution-${resolvedActiveSelectionId.replace('selection-', '')}`
                : topologySolution.graph.id,
              selection: {
                ...topologySolution.graph.selection,
                id: resolvedActiveSelectionId ?? topologySolution.graph.selection.id,
                selection: activeSelection,
              },
            },
          }
        : undefined,
    [activeSelection, resolvedActiveSelectionId, topologySolution],
  )
  const solutionPending =
    deferredTopologyRequest !== topologyRequest || solutionIdentityPending
  useEffect(() => {
    setActiveLayout((current) =>
      current?.requestId === solution?.cacheKey ? current : undefined,
    )
  }, [solution?.cacheKey])
  const graph = solution?.graph ?? sourceGraph
  const nodeById = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph])
  const edgeById = useMemo(
    () =>
      new Map(
        [
          ...graph.edges,
          ...(solution?.internalInterfaces ?? []),
          ...(solution?.boundaryInterfaces.map((item) => item.interface) ?? []),
        ].map((edge) => [edge.id, edge]),
      ),
    [graph, solution],
  )
  const catalogGraphId = data.diagramCatalogByGraph[graph.id] ? graph.id : sourceGraph.id
  const canonicalByLikec4Id = useMemo(
    () =>
      new Map(
        Object.entries(data.canonicalToLikec4ByGraph[catalogGraphId] ?? {}).map(
          ([canonical, likec4]) => [likec4, canonical],
        ),
      ),
    [catalogGraphId, data],
  )
  const interfaceByLikec4EdgeId = useMemo(
    () => new Map(Object.entries(data.likec4EdgeToCanonicalByGraph[catalogGraphId] ?? {})),
    [catalogGraphId, data],
  )
  const diagramCatalog = data.diagramCatalogByGraph[catalogGraphId] ?? []
  const selectedDiagramId = state.diagramId?.split('/')[0]
  const selectedDiagram = diagramCatalog.find((diagram) => diagram.id === selectedDiagramId)

  const update = useCallback((updater: (current: ExplorerState) => ExplorerState) => {
    setState((current) => updater(current))
  }, [])
  const updateSolution = useCallback((updater: (current: ExplorerState) => ExplorerState) => {
    setState((current) => {
      const next = updater(current)
      const entry = historyEntry(next)
      const bounded = appendBoundedHistory(
        solutionHistory.current,
        solutionHistoryIndex.current,
        entry,
      )
      solutionHistory.current = bounded.history
      solutionHistoryIndex.current = bounded.index
      return next
    })
    setHistoryVersion((version) => version + 1)
  }, [])
  const setGraph = useCallback(
    (graphId: string) => {
      if (!graphById.has(graphId)) return
      updateSolution((current) => ({ ...current, graphId, selectedId: undefined }))
    },
    [graphById, updateSolution],
  )
  const setBrowseBy = useCallback(
    (browseBy: BrowseGroup) =>
      updateSolution((current) => ({ ...current, browseBy, subject: undefined })),
    [updateSolution],
  )
  const setSubject = useCallback(
    (subject?: string) =>
      updateSolution((current) => ({
        ...current,
        subject,
        systemSet: selectorFor(current.browseBy, subject),
      })),
    [updateSolution],
  )
  const setSearch = useCallback(
    (search: string) => update((current) => ({ ...current, search })),
    [update],
  )
  const setSnapshotOrder = useCallback(
    (snapshotOrder: number) =>
      updateSolution((current) => ({ ...current, snapshotOrder })),
    [updateSolution],
  )
  const setInterfaceDepth = useCallback(
    (interfaceDepth: number) =>
      updateSolution((current) => ({ ...current, interfaceDepth })),
    [updateSolution],
  )
  const setLevel = useCallback(
    (level: ArchitectureLevel) => updateSolution((current) => ({ ...current, level })),
    [updateSolution],
  )
  const setColorBy = useCallback(
    (colorBy: ColorBy) => updateSolution((current) => ({ ...current, colorBy })),
    [updateSolution],
  )
  const setDiagram = useCallback(
    (diagramId?: string) => update((current) => withDiagram(current, diagramId)),
    [update],
  )
  const selectEntity = useCallback(
    (selectedId?: string) =>
      update((current) => ({
        ...current,
        selectedId,
        inspectorOpen: selectedId !== undefined,
      })),
    [update],
  )
  const setDataOpen = useCallback(
    (dataOpen: boolean) => update((current) => ({ ...current, dataOpen })),
    [update],
  )
  const setInspectorOpen = useCallback(
    (inspectorOpen: boolean) => update((current) => ({ ...current, inspectorOpen })),
    [update],
  )
  const setActiveTable = useCallback(
    (activeTable: ExplorerState['activeTable']) =>
      update((current) => ({ ...current, activeTable })),
    [update],
  )
  const updatePreferences = useCallback(
    (updater: (preferences: ExplorerPreferences) => ExplorerPreferences) => {
      update((current) => {
        const preferences = updater(current.preferences)
        if (typeof window !== 'undefined') savePreferences(window.localStorage, preferences)
        return { ...current, preferences }
      })
    },
    [update],
  )
  const setDensity = useCallback(
    (density: Density) => updatePreferences((current) => ({ ...current, density })),
    [updatePreferences],
  )
  const setColorScheme = useCallback(
    (colorScheme: ExplorerPreferences['colorScheme']) =>
      updatePreferences((current) => ({ ...current, colorScheme })),
    [updatePreferences],
  )
  const setTableLayout = useCallback(
    (tableId: string, layout: unknown[]) =>
      updatePreferences((current) => ({
        ...current,
        tableLayouts: { ...current.tableLayouts, [tableId]: layout },
      })),
    [updatePreferences],
  )
  const reportDiagnostic = useCallback(
    (diagnostic: string) =>
      update((current) =>
        current.diagnostics.includes(diagnostic)
          ? current
          : { ...current, diagnostics: [...current.diagnostics, diagnostic] },
      ),
    [update],
  )
  const resetPreferences = useCallback(
    () => {
      if (typeof window !== 'undefined') window.localStorage.removeItem(PREFERENCES_KEY)
      update((current) => ({ ...current, preferences: DEFAULT_PREFERENCES }))
    },
    [update],
  )
  const goBack = useCallback(() => {
    if (solutionHistoryIndex.current === 0) return
    solutionHistoryIndex.current -= 1
    const entry = solutionHistory.current[solutionHistoryIndex.current]!
    update((current) => ({ ...current, ...entry, selectedId: undefined }))
    setHistoryVersion((version) => version + 1)
  }, [update])
  const goForward = useCallback(() => {
    if (solutionHistoryIndex.current >= solutionHistory.current.length - 1) return
    solutionHistoryIndex.current += 1
    const entry = solutionHistory.current[solutionHistoryIndex.current]!
    update((current) => ({ ...current, ...entry, selectedId: undefined }))
    setHistoryVersion((version) => version + 1)
  }, [update])

  useEffect(() => {
    const hash = serializeFragment({
      graph: state.graphId,
      order: state.snapshotOrder,
      depth: state.interfaceDepth,
      colorBy: state.colorBy,
      browse: state.browseBy,
      subject: state.subject,
      search: state.search,
      diagram: state.diagramId,
      selected: state.selectedId,
      dataOpen: state.dataOpen,
      inspectorOpen: state.inspectorOpen,
      activeTable: state.activeTable,
      systemSet: state.systemSet,
      compare: graph.selection.selection.compare_from?.toString(),
      level: state.level,
      visibility: graph.selection.selection.visibility,
      statuses: graph.selection.selection.display_statuses,
    })
    if (window.location.hash !== hash) window.history.replaceState(null, '', hash)
  }, [graph, state])

  const actions = useMemo<ExplorerActions>(
    () => ({
      setGraph,
      setBrowseBy,
      setSubject,
      setSearch,
      setSnapshotOrder,
      setInterfaceDepth,
      setLevel,
      setColorBy,
      setDiagram,
      selectEntity,
      setDataOpen,
      setInspectorOpen,
      setActiveTable,
      setDensity,
      setColorScheme,
      setTableLayout,
      reportDiagnostic,
      resetPreferences,
      setActiveLayout,
      goBack,
      goForward,
    }),
    [
      reportDiagnostic,
      resetPreferences,
      setActiveLayout,
      selectEntity,
      setBrowseBy,
      setColorScheme,
      setDataOpen,
      setDensity,
      setDiagram,
      setGraph,
      setInspectorOpen,
      setActiveTable,
      setSearch,
      setSnapshotOrder,
      setInterfaceDepth,
      setLevel,
      setColorBy,
      setSubject,
      setTableLayout,
      goBack,
      goForward,
    ],
  )
  const meta = useMemo<ExplorerMeta>(
    () => ({
      data,
      graph,
      nodeById,
      edgeById,
      likec4ViewId:
        selectedDiagram?.likec4View ?? data.likec4ViewByGraph[catalogGraphId] ?? 'index',
      canonicalByLikec4Id,
      interfaceByLikec4EdgeId,
      diagramCatalog,
      selectedDiagram,
      hoveredId,
      solution,
      prepared,
      activeLayout,
      solutionPending,
      solutionIdentityPending,
      canGoBack: solutionHistoryIndex.current > 0,
      canGoForward: solutionHistoryIndex.current < solutionHistory.current.length - 1,
    }),
    [activeLayout, canonicalByLikec4Id, data, diagramCatalog, edgeById, graph, historyVersion, interfaceByLikec4EdgeId, nodeById, prepared, selectedDiagram, solution, solutionIdentityPending, solutionPending],
  )
  const value = useMemo<ExplorerContextValue>(() => ({ state, actions, meta }), [actions, meta, state])

  return <ExplorerContext value={value}>{children}</ExplorerContext>
}
