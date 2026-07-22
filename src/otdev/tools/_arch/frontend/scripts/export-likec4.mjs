import { generateDrawio, generateDrawioMulti } from '@likec4/generators'
import { LikeC4 } from 'likec4'

process.stdin.setEncoding('utf8')
let input = ''
for await (const chunk of process.stdin) input += chunk
const request = JSON.parse(input)
const api = await LikeC4.fromSource(request.source, {
  graphviz: 'wasm',
  logger: false,
  printErrors: false,
  throwIfInvalid: true,
})
const model = await api.layoutedModel()
const views = request.viewIds.map((viewId) => {
  const view = model.view(viewId)
  if (!view) throw new Error(`Unknown layouted view '${viewId}'`)
  const raw = view.$view
  return {
    id: viewId,
    title: raw.title ?? viewId,
    bounds: raw.bounds,
    nodes: raw.nodes.map((node) => ({
      id: node.id,
      title: node.title,
      x: node.x,
      y: node.y,
      width: node.width,
      height: node.height,
      parent: node.parent,
      shape: node.shape,
      color: node.color,
      links: node.links,
    })),
    edges: raw.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      points: edge.points,
      color: edge.color,
      relations: edge.relations,
      canonicalIds: edge.relations
        .map((relationId) => model.relationship(relationId).getMetadata('canonicalId'))
        .filter((value) => typeof value === 'string'),
    })),
    drawio: generateDrawio(view, {
      compressed: false,
      modified: '2026-01-01T00:00:00.000Z',
    }),
  }
})
const multiDrawio = generateDrawioMulti(
  request.viewIds.map((viewId) => model.view(viewId)),
  undefined,
  '2026-01-01T00:00:00.000Z',
)
process.stdout.write(JSON.stringify({ views, multiDrawio }))
