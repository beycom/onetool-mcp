import {
  Box,
  type BoxProps,
  createVarsResolver,
  type ElementProps,
  factory,
  type Factory,
  type StylesApiProps,
  useProps,
  useStyles,
} from '@mantine/core'

import type { TransitionStatus } from '../data/types'
import classes from './StatusMark.module.css'

const STATUS = {
  'No Change': { color: '#82B366', cue: '●', label: 'No Change', border: 'solid' },
  Changed: { color: '#D6B656', cue: '△', label: 'Changed', border: 'solid' },
  Added: { color: '#6C8EBF', cue: '+', label: 'Added', border: 'double' },
  Removed: { color: '#B85450', cue: '×', label: 'Removed', border: 'double' },
} as const satisfies Record<TransitionStatus, { color: string; cue: string; label: string; border: string }>

export interface StatusMarkProps
  extends BoxProps,
    StylesApiProps<StatusMarkFactory>,
    ElementProps<'span'> {
  status: TransitionStatus
}

export type StatusMarkFactory = Factory<{
  props: StatusMarkProps
  ref: HTMLSpanElement
  stylesNames: 'root' | 'cue'
  vars: { root: '--status-color' | '--status-border-style' }
}>

const varsResolver = createVarsResolver<StatusMarkFactory>((_theme, { status }) => ({
  root: {
    '--status-color': STATUS[status].color,
    '--status-border-style': STATUS[status].border,
  },
}))

export const StatusMark = factory<StatusMarkFactory>((_props) => {
  const props = useProps('StatusMark', {}, _props)
  const {
    attributes,
    className,
    classNames,
    status,
    style,
    styles,
    unstyled,
    vars,
    ...others
  } = props
  const getStyles = useStyles<StatusMarkFactory>({
    name: 'StatusMark',
    classes,
    props,
    attributes,
    className,
    classNames,
    style,
    styles,
    unstyled,
    vars,
    varsResolver,
  })
  const definition = STATUS[status]
  return (
    <Box component="span" data-status={status} {...getStyles('root')} {...others}>
      <span aria-hidden="true" {...getStyles('cue')}>
        {definition.cue}
      </span>
      {definition.label}
    </Box>
  )
})

StatusMark.displayName = 'StatusMark'
StatusMark.classes = classes
StatusMark.varsResolver = varsResolver
