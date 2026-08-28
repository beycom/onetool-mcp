import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

function Icon({ children, ...props }: IconProps) {
  return (
    <svg aria-hidden="true" fill="none" height="16" viewBox="0 0 16 16" width="16" {...props}>
      <g stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5">{children}</g>
    </svg>
  )
}

export function SearchIcon(props: IconProps) {
  return <Icon {...props}><circle cx="7" cy="7" r="4" /><path d="m10 10 3 3" /></Icon>
}

export function CopyIcon(props: IconProps) {
  return <Icon {...props}><rect height="8" rx="1.5" width="8" x="5" y="5" /><path d="M3 10V4.5A1.5 1.5 0 0 1 4.5 3H10" /></Icon>
}

export function MapIcon(props: IconProps) {
  return <Icon {...props}><path d="m2.5 3.5 3-1.5 5 2 3-1.5v10l-3 1.5-5-2-3 1.5zM5.5 2v10M10.5 4v10" /></Icon>
}

export function FitIcon(props: IconProps) {
  return <Icon {...props}><path d="M6 3H3v3M10 3h3v3M6 13H3v-3M10 13h3v-3" /></Icon>
}
