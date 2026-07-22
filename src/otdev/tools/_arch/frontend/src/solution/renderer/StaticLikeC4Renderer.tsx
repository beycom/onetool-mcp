import { LikeC4ModelProvider, ReactLikeC4 } from 'likec4:react'

import { LikeC4AdapterNode } from './LikeC4AdapterNode'

export function StaticRendererProvider({ children }: { children: React.ReactNode }) {
  return <LikeC4ModelProvider>{children}</LikeC4ModelProvider>
}

export function StaticLikeC4Renderer({
  viewId,
  canonicalByRendererId,
  interfacesByRendererEdgeId,
  onSelect,
}: {
  viewId: string
  canonicalByRendererId: ReadonlyMap<string, string>
  interfacesByRendererEdgeId: ReadonlyMap<string, string[]>
  onSelect: (id: string) => void
}) {
  return (
    <ReactLikeC4
      background="dots"
      enableElementDetails
      enableFocusMode
      enableRelationshipBrowser
      enableRelationshipDetails
      enableSearch
      injectFontCss={false}
      keepAspectRatio
      nodesSelectable
      onEdgeClick={(edge) =>
        onSelect(interfacesByRendererEdgeId.get(edge.id)?.[0] ?? edge.id)
      }
      onNodeClick={(node) => onSelect(canonicalByRendererId.get(node.id) ?? node.id)}
      pannable
      reduceGraphics="auto"
      renderNodes={{ element: LikeC4AdapterNode }}
      showNavigationButtons
      viewId={viewId as never}
      zoomable
    />
  )
}
