import {
  DefaultHandles,
  ElementActions,
  ElementData,
  ElementDetailsButtonWithHandler,
  elementNode,
  ElementNodeContainer,
  ElementShape,
} from 'likec4/react'

export const LikeC4AdapterNode = elementNode(({ nodeProps, nodeModel }) => {
  const status = String(nodeModel.element.getMetadata('status') ?? 'No Change')
  const contextStatus = String(nodeModel.element.getMetadata('contextStatus') ?? 'no_change')
  return (
    <ElementNodeContainer
      data-context-status={contextStatus}
      data-onetool-node="true"
      data-status={status}
      nodeProps={nodeProps}
    >
      <ElementShape {...nodeProps} />
      <ElementData {...nodeProps} />
      <span aria-label={`Status: ${status}`} className="diagram-status-cue">
        {status === 'Added' ? '+' : status === 'Removed' ? '×' : status === 'Changed' ? '△' : '●'}
      </span>
      <ElementActions {...nodeProps} />
      <ElementDetailsButtonWithHandler {...nodeProps} />
      <DefaultHandles />
    </ElementNodeContainer>
  )
})
