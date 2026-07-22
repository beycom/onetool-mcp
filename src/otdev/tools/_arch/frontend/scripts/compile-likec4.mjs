import { LikeC4 } from 'likec4'

process.stdin.setEncoding('utf8')
let source = ''
for await (const chunk of process.stdin) source += chunk
try {
  const api = await LikeC4.fromSource(source, {
    graphviz: 'wasm',
    logger: false,
    printErrors: false,
    throwIfInvalid: true,
  })
  const model = await api.layoutedModel()
  const views = [...model.views()].map((view) => ({
    id: view.id,
    nodes: view.$view.nodes.length,
    edges: view.$view.edges.length,
    width: view.$view.bounds.width,
    height: view.$view.bounds.height,
    edgeMappings: Object.fromEntries(
      view.$view.edges.map((edge) => [
        edge.id,
        edge.relations
          .map((relationId) => model.relationship(relationId).getMetadata('canonicalId'))
          .filter((value) => typeof value === 'string'),
      ]),
    ),
  }))
  process.stdout.write(JSON.stringify({ views }))
} catch (error) {
  const errors = typeof error?.getErrors === 'function' ? error.getErrors() : null
  process.stderr.write(JSON.stringify(errors ?? { message: String(error) }))
  process.exitCode = 1
}
