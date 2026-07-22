import '@fontsource-variable/ibm-plex-sans'
import '@fontsource/ibm-plex-mono/400.css'

import {
  Alert,
  Breadcrumbs,
  Button,
  ColorSchemeScript,
  createTheme,
  Group,
  MantineProvider,
  Menu,
  Modal,
  Select,
  Stack,
  Text,
  Title,
  useMantineColorScheme,
} from '@mantine/core'
import { useEffect, useState } from 'react'
import architectureData from 'virtual:onetool-data'

import type { DiagramAttachment, DiagramCatalogItem } from './data/types'
import { ExplorerDataRegion } from './explorer/ExplorerDataRegion'
import { ExplorerInspector } from './explorer/ExplorerInspector'
import { ExplorerNavigation } from './explorer/ExplorerScreens'
import { ExplorerProvider, useExplorer } from './explorer/ExplorerProvider'
import { ExplorerShell } from './explorer/ExplorerShell'
import { StatusMark } from './explorer/StatusMark'
import { DynamicSolutionDiagram } from './solution/DynamicSolutionDiagram'
import { solutionColors } from './solution/colors'
import { downloadDrawio, drawioFilename, drawioPageName, drawioXml } from './solution/drawio'
import { SolutionSummary } from './solution/SolutionSummary'
import {
  StaticLikeC4Renderer,
  StaticRendererProvider,
} from './solution/renderer/StaticLikeC4Renderer'

const theme = createTheme({
  fontFamily: 'IBM Plex Sans Variable, system-ui, sans-serif',
  fontFamilyMonospace: 'IBM Plex Mono, monospace',
  primaryColor: 'cyan',
  defaultRadius: 'sm',
  components: {
    ExplorerShell: ExplorerShell.extend({
      defaultProps: { navigationWidth: '17rem', inspectorWidth: '20rem' },
    }),
    StatusMark: StatusMark.extend({}),
  },
})

function ColorSchemeMenu() {
  const { state, actions } = useExplorer()
  const { setColorScheme } = useMantineColorScheme()
  useEffect(() => {
    setColorScheme(state.preferences.colorScheme)
  }, [setColorScheme, state.preferences.colorScheme])
  return (
    <Menu position="bottom-end">
      <Menu.Target>
        <Button aria-label="Color scheme" variant="default">
          Theme: {state.preferences.colorScheme}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {(['auto', 'light', 'dark'] as const).map((scheme) => (
          <Menu.Item
            key={scheme}
            onClick={() => {
              actions.setColorScheme(scheme)
              setColorScheme(scheme)
            }}
          >
            {scheme[0].toUpperCase() + scheme.slice(1)}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  )
}

function ExportMenu() {
  const { state, meta } = useExplorer()
  const ready =
    !meta.solutionPending &&
    meta.solution !== undefined &&
    meta.activeLayout?.requestId === meta.solution.cacheKey &&
    meta.activeLayout.graphId === meta.graph.id &&
    meta.activeLayout.selectionId === meta.graph.selection.id
  const exportDrawio = () => {
    if (!ready || !meta.activeLayout) return
    const colors = solutionColors(meta.graph, state.colorBy, meta.data.presentation)
    const content = drawioXml({
      graph: meta.graph,
      layout: meta.activeLayout,
      nodeColors: colors.nodeColors,
      nodeBorders: colors.nodeBorders,
      edgeColors: colors.edgeColors,
      pageName: drawioPageName(meta.graph),
    })
    downloadDrawio(drawioFilename(meta.graph), content)
  }
  return (
    <Menu position="bottom-end">
      <Menu.Target>
        <Button aria-label="Export solution" variant="default">Export</Button>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Item disabled={!ready} onClick={exportDrawio}>Draw.io</Menu.Item>
      </Menu.Dropdown>
    </Menu>
  )
}

function ExplorerCanvas() {
  const { state, actions, meta } = useExplorer()
  const selectionFocusId = state.selectedId
    ? (meta.solution?.boundaryInterfaces.find(
        (item) => item.interface.id === state.selectedId,
      )?.inside_system ??
      meta.solution?.collapsedInterfaces.find(
        (item) => item.interface.id === state.selectedId,
      )?.visible_node)
    : undefined
  const catalogDiagram = meta.selectedDiagram?.kind !== 'generated' ? meta.selectedDiagram : undefined
  const attachment = catalogDiagram?.attachmentId
    ? meta.data.attachments[catalogDiagram.attachmentId]
    : undefined
  return (
    <>
      {meta.solution && !catalogDiagram ? <SolutionSummary /> : null}
      {catalogDiagram?.kind === 'external' ? (
        <ExternalDiagram attachment={attachment} diagram={catalogDiagram} />
      ) : catalogDiagram?.likec4View ? (
        <StaticLikeC4Renderer
          canonicalByRendererId={meta.canonicalByLikec4Id}
          interfacesByRendererEdgeId={meta.interfaceByLikec4EdgeId}
          onSelect={actions.selectEntity}
          viewId={catalogDiagram.likec4View}
        />
      ) : meta.solution ? (
        <DynamicSolutionDiagram
          cacheKey={meta.solution.cacheKey}
          colorBy={state.colorBy}
          graph={meta.graph}
          onLayout={actions.setActiveLayout}
          onReduceDepth={() => actions.setInterfaceDepth(Math.max(0, state.interfaceDepth - 1))}
          onSelect={(id) => actions.selectEntity(id)}
          pending={meta.solutionPending}
          presentation={meta.data.presentation}
          selectionFocusId={selectionFocusId}
          selectedId={state.selectedId}
        />
      ) : (
        <StaticLikeC4Renderer
          canonicalByRendererId={meta.canonicalByLikec4Id}
          interfacesByRendererEdgeId={meta.interfaceByLikec4EdgeId}
          onSelect={actions.selectEntity}
          viewId={meta.likec4ViewId}
        />
      )}
      <Group className="canvas-toolbar" gap="xs">
        <Button onClick={() => actions.setDataOpen(!state.dataOpen)} size="compact-sm">
          {state.dataOpen ? 'Hide data' : 'Show data'}
        </Button>
        <Button
          onClick={() => actions.setInspectorOpen(!state.inspectorOpen)}
          size="compact-sm"
          variant="default"
        >
          {state.inspectorOpen ? 'Hide details' : 'Show details'}
        </Button>
      </Group>
    </>
  )
}

function ExternalDiagram({
  attachment,
  diagram,
}: {
  attachment?: DiagramAttachment
  diagram: DiagramCatalogItem
}) {
  if (!attachment) {
    return (
      <Alert color="red" title="Attachment unavailable">
        The selected diagram attachment could not be loaded.
      </Alert>
    )
  }
  if (attachment.mediaType === 'image/svg+xml') {
    return <img alt={diagram.name} className="external-diagram" src={attachment.dataUrl} />
  }
  return (
    <iframe
      className="external-diagram"
      loading="lazy"
      sandbox=""
      src={attachment.dataUrl}
      title={diagram.name}
    />
  )
}

function ExplorerWorkspace() {
  const [aboutOpen, setAboutOpen] = useState(false)
  const { state, actions, meta } = useExplorer()
  const roadmapId =
    meta.graph.selection.roadmap_id ??
    meta.data.presentation.default_roadmap ??
    Object.keys(meta.data.solutionSnapshots)[0]
  const prepared = roadmapId ? meta.data.solutionSnapshots[roadmapId] : undefined
  const snapshotOptions = Object.entries(prepared?.snapshots ?? {}).map(([order, graph]) => ({
    value: order,
    label: `Order ${order}: ${graph.selection.through ?? graph.selection.state_id}`,
  }))
  const diagramOptions = meta.diagramCatalog
    .filter((diagram) => diagram.kind !== 'generated')
    .map((diagram) => ({ value: diagram.id, label: diagram.name }))
  return (
    <>
      <a className="skip-link" href="#architecture-canvas">
        Skip to architecture canvas
      </a>
      <ExplorerShell
        data-active-edges={JSON.stringify(meta.graph.edges.map((edge) => edge.id))}
        data-active-graph={state.graphId}
        data-active-selection={meta.graph.selection.id}
        data-active-solution={meta.graph.id}
        id="main-content"
      >
        <ExplorerShell.Header>
          <div>
            <Text className="eyebrow">OneTool</Text>
            <Group gap="xs" wrap="nowrap">
              <Button
                aria-label="Back in solution history"
                disabled={!meta.canGoBack}
                onClick={actions.goBack}
                size="compact-xs"
                variant="subtle"
              >
                ←
              </Button>
              <Button
                aria-label="Forward in solution history"
                disabled={!meta.canGoForward}
                onClick={actions.goForward}
                size="compact-xs"
                variant="subtle"
              >
                →
              </Button>
              <Breadcrumbs aria-label="Solution location" separator="/">
                <Text size="xs">Solution</Text>
                <Text size="xs">{state.subject ?? 'All systems'}</Text>
              </Breadcrumbs>
            </Group>
            <Title order={1} size="h3">
              {meta.data.title}
            </Title>
          </div>
          <Group>
            <Select
              aria-label="Roadmap snapshot"
              data={snapshotOptions}
              onChange={(value) => value !== null && actions.setSnapshotOrder(Number(value))}
              value={String(state.snapshotOrder)}
            />
            <Select
              aria-label="Architectural level"
              data={[
                { value: 'system', label: 'System' },
                { value: 'application', label: 'Application' },
                { value: 'component', label: 'Component' },
              ]}
              onChange={(value) =>
                value && actions.setLevel(value as 'system' | 'application' | 'component')
              }
              value={state.level}
            />
            <Select
              aria-label="Interface depth"
              data={['0', '1', '2', '3']}
              onChange={(value) => value !== null && actions.setInterfaceDepth(Number(value))}
              value={String(state.interfaceDepth)}
            />
            <Select
              aria-label="Color by"
              data={[
                { value: 'change_status', label: 'Change status' },
                { value: 'integration_type', label: 'Integration type' },
                { value: 'tag', label: 'Tag' },
              ]}
              onChange={(value) =>
                value && actions.setColorBy(value as 'change_status' | 'integration_type' | 'tag')
              }
              value={state.colorBy}
            />
            {diagramOptions.length > 0 ? (
              <Select
                aria-label="Diagram view"
                clearable
                data={diagramOptions}
                onChange={(value) => actions.setDiagram(value ?? undefined)}
                placeholder="Architecture"
                value={state.diagramId ?? null}
              />
            ) : null}
            <ColorSchemeMenu />
            <ExportMenu />
            <Button onClick={() => setAboutOpen(true)} variant="subtle">
              About
            </Button>
          </Group>
        </ExplorerShell.Header>

        <ExplorerShell.Navigation>
          <ExplorerNavigation />
        </ExplorerShell.Navigation>

        <ExplorerShell.Canvas id="architecture-canvas" tabIndex={-1}>
          <ExplorerCanvas />
        </ExplorerShell.Canvas>

        {state.inspectorOpen ? (
          <ExplorerShell.Inspector>
            <ExplorerInspector />
          </ExplorerShell.Inspector>
        ) : null}

        {state.dataOpen ? (
          <ExplorerShell.DataRegion>
            <ExplorerDataRegion />
          </ExplorerShell.DataRegion>
        ) : null}
      </ExplorerShell>

      {state.diagnostics.length > 0 ? (
        <aside aria-label="Diagnostics" className="diagnostics-region">
          <Stack gap="xs">
            {state.diagnostics.map((diagnostic) => (
              <Alert color="yellow" key={diagnostic} title="Architecture diagnostic">
                {diagnostic}
              </Alert>
            ))}
          </Stack>
        </aside>
      ) : null}

      <Modal onClose={() => setAboutOpen(false)} opened={aboutOpen} title="OneTool Architecture">
        <Text size="sm">
          This self-contained explorer uses a locally bundled solution renderer and AG Grid
          Community. Architecture states are resolved before this page is
          generated; the browser never replays roadmap mutations.
        </Text>
      </Modal>
    </>
  )
}

export function App() {
  return (
    <>
      <ColorSchemeScript defaultColorScheme="auto" />
      <MantineProvider defaultColorScheme="auto" theme={theme}>
        <StaticRendererProvider>
          <ExplorerProvider data={architectureData}>
            <ExplorerWorkspace />
          </ExplorerProvider>
        </StaticRendererProvider>
      </MantineProvider>
    </>
  )
}
