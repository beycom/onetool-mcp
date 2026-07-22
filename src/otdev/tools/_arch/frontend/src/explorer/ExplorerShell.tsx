import {
  Box,
  type BoxProps,
  createSafeContext,
  createVarsResolver,
  type ElementProps,
  factory,
  type Factory,
  type GetStylesApi,
  type StylesApiProps,
  useProps,
  useStyles,
} from '@mantine/core'

import classes from './ExplorerShell.module.css'

export type ExplorerShellStylesNames =
  | 'root'
  | 'header'
  | 'navigation'
  | 'canvas'
  | 'inspector'
  | 'dataRegion'

export type ExplorerShellCssVariables = {
  root: '--explorer-navigation-width' | '--explorer-inspector-width'
}

export interface ExplorerShellProps
  extends BoxProps,
    StylesApiProps<ExplorerShellFactory>,
    ElementProps<'main'> {
  navigationWidth?: string
  inspectorWidth?: string
}

interface RegionProps extends BoxProps, ElementProps<'div'> {
  children?: React.ReactNode
  className?: string
  style?: React.CSSProperties
}

type RegionFactory = Factory<{
  props: RegionProps
  ref: HTMLElement
  compound: true
}>

export type ExplorerShellFactory = Factory<{
  props: ExplorerShellProps
  ref: HTMLElement
  stylesNames: ExplorerShellStylesNames
  vars: ExplorerShellCssVariables
  staticComponents: {
    Header: typeof ExplorerShellHeader
    Navigation: typeof ExplorerShellNavigation
    Canvas: typeof ExplorerShellCanvas
    Inspector: typeof ExplorerShellInspector
    DataRegion: typeof ExplorerShellDataRegion
  }
}>

interface ExplorerShellContextValue {
  getStyles: GetStylesApi<ExplorerShellFactory>
}

const [ExplorerShellContext, useExplorerShell] = createSafeContext<ExplorerShellContextValue>(
  'ExplorerShell region must be rendered within ExplorerShell',
)

function createRegion(
  displayName: string,
  selector: ExplorerShellStylesNames,
  component: 'header' | 'nav' | 'section' | 'aside',
  ariaLabel?: string,
) {
  const Region = factory<RegionFactory>(({ children, className, style, ...others }) => {
    const { getStyles } = useExplorerShell()
    return (
      <Box
        aria-label={ariaLabel}
        component={component}
        {...getStyles(selector, { className, style })}
        {...others}
      >
        {children}
      </Box>
    )
  })
  Region.displayName = displayName
  return Region
}

const ExplorerShellHeader = createRegion('ExplorerShell.Header', 'header', 'header')
const ExplorerShellNavigation = createRegion(
  'ExplorerShell.Navigation',
  'navigation',
  'nav',
  'Architecture browsing',
)
const ExplorerShellCanvas = createRegion(
  'ExplorerShell.Canvas',
  'canvas',
  'section',
  'Architecture diagram',
)
const ExplorerShellInspector = createRegion(
  'ExplorerShell.Inspector',
  'inspector',
  'aside',
  'Selection details',
)
const ExplorerShellDataRegion = createRegion(
  'ExplorerShell.DataRegion',
  'dataRegion',
  'section',
  'Architecture data',
)

const defaultProps = {
  navigationWidth: '17rem',
  inspectorWidth: '20rem',
} satisfies Partial<ExplorerShellProps>

const varsResolver = createVarsResolver<ExplorerShellFactory>(
  (_theme, { inspectorWidth, navigationWidth }) => ({
    root: {
      '--explorer-inspector-width': inspectorWidth,
      '--explorer-navigation-width': navigationWidth,
    },
  }),
)

export const ExplorerShell = factory<ExplorerShellFactory>((_props) => {
  const props = useProps('ExplorerShell', defaultProps, _props)
  const {
    attributes,
    children,
    className,
    classNames,
    inspectorWidth,
    navigationWidth,
    style,
    styles,
    unstyled,
    vars,
    ...others
  } = props
  const getStyles = useStyles<ExplorerShellFactory>({
    name: 'ExplorerShell',
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

  return (
    <ExplorerShellContext value={{ getStyles }}>
      <Box component="main" {...getStyles('root')} {...others}>
        {children}
      </Box>
    </ExplorerShellContext>
  )
})

ExplorerShell.displayName = 'ExplorerShell'
ExplorerShell.classes = classes
ExplorerShell.varsResolver = varsResolver
ExplorerShell.Header = ExplorerShellHeader
ExplorerShell.Navigation = ExplorerShellNavigation
ExplorerShell.Canvas = ExplorerShellCanvas
ExplorerShell.Inspector = ExplorerShellInspector
ExplorerShell.DataRegion = ExplorerShellDataRegion

export namespace ExplorerShell {
  export type Props = ExplorerShellProps
  export type StylesNames = ExplorerShellStylesNames
  export type CssVariables = ExplorerShellCssVariables
  export type Factory = ExplorerShellFactory
}
