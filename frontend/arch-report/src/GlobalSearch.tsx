import { useEffect, useMemo, useRef, useState } from 'react'

import { SearchIcon } from './Icons'

export type SearchResult = {
  id: string
  kind: string
  label: string
  meta: string
  onChoose: () => void
}

function rank(result: SearchResult, query: string): number {
  const label = result.label.toLocaleLowerCase()
  const id = result.id.toLocaleLowerCase()
  if (label === query || id === query) return 0
  if (label.startsWith(query)) return 1
  if (id.startsWith(query)) return 2
  if (label.includes(query)) return 3
  if (id.includes(query)) return 4
  return 5
}

export function GlobalSearch({ onClose, results }: { onClose: () => void; results: SearchResult[] }) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const dialog = useRef<HTMLElement>(null)
  const visible = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase()
    const matches = normalized
      ? results.filter((result) => `${result.label}\n${result.id}`.toLocaleLowerCase().includes(normalized))
      : results
    return matches.sort((left, right) => rank(left, normalized) - rank(right, normalized) || left.label.localeCompare(right.label)).slice(0, 30)
  }, [query, results])

  useEffect(() => { input.current?.focus() }, [])
  useEffect(() => { setActive(0) }, [query])

  const choose = (result: SearchResult | undefined) => {
    if (!result) return
    result.onChoose()
    onClose()
  }

  return (
    <div aria-label="Global search" aria-modal="true" className="search-scrim" role="dialog" onKeyDown={(event) => {
      if (event.key !== 'Tab') return
      const focusable = [...(dialog.current?.querySelectorAll<HTMLElement>('input, button, [href], [tabindex]:not([tabindex="-1"])') ?? [])]
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable.at(-1)!
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }} onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section className="search-dialog" ref={dialog}>
        <label className="search-input"><SearchIcon /><input
          aria-label="Search diagrams and model"
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') { event.preventDefault(); setActive((value) => Math.min(value + 1, visible.length - 1)) }
            if (event.key === 'ArrowUp') { event.preventDefault(); setActive((value) => Math.max(0, value - 1)) }
            if (event.key === 'Enter') { event.preventDefault(); choose(visible[active]) }
            if (event.key === 'Escape') { event.preventDefault(); onClose() }
          }}
          placeholder="Search diagrams, entities, interfaces"
          ref={input}
          type="search"
          value={query}
        /><kbd>Esc</kbd></label>
        <div aria-label="Search results" className="search-results" role="listbox">
          {visible.map((result, index) => <button aria-selected={index === active} key={`${result.kind}:${result.id}`} onClick={() => choose(result)} onMouseEnter={() => setActive(index)} role="option" type="button"><span><strong>{result.label}</strong><small>{result.id}</small></span><em>{result.meta}</em></button>)}
          {!visible.length ? <p>No matching items</p> : null}
        </div>
      </section>
    </div>
  )
}
