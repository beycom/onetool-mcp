import { useCallback, useState } from 'react'

import { ArchitectureCanvas } from './ArchitectureCanvas'
import { passports, type DiagramMode, type DiagramTab, type PassportRecord } from './data'
import { SequenceCanvas } from './SequenceCanvas'
import { useDraggablePanel } from './useDraggablePanel'

function Passport({
  copied,
  onClose,
  onCopy,
  onSelect,
  record,
}: {
  copied: boolean
  onClose: () => void
  onCopy: () => void
  onSelect: (record: PassportRecord) => void
  record: PassportRecord
}) {
  const { dragHandleProps, panelRef } = useDraggablePanel<HTMLElement>('semantic passport')
  const passportType = record.kind === 'relationship' || record.kind === 'message'
    ? 'RELATIONSHIP PASSPORT'
    : 'SEMANTIC PASSPORT'

  return (
    <aside aria-label={`Details for ${record.name}`} className="draggable-panel semantic-passport" ref={panelRef}>
      <header className="passport-header">
        <div>
          <span className="panel-kicker">{passportType}</span>
          <h2>{record.name}</h2>
          <p>{record.subtitle}</p>
        </div>
        <div className="panel-header-actions">
          <button className="panel-drag-handle" type="button" {...dragHandleProps}><span aria-hidden="true">⠿</span></button>
          <button aria-label="Close semantic passport" className="icon-button" onClick={onClose} type="button">×</button>
        </div>
      </header>

      <div className="passport-meta-row">
        <div className="passport-chips">
          {record.tags.map((tag, index) => (
            <span className={index === 0 ? 'primary-chip' : ''} key={tag}>{tag}</span>
          ))}
        </div>
        <button className="copy-action" onClick={onCopy} type="button">{copied ? 'Copied' : 'Copy link'}</button>
      </div>

      <p className="passport-context">{record.context}</p>
      {record.note ? <p className="passport-note">{record.note}</p> : null}
      <p className="passport-counts">{record.outgoing} outgoing · {record.incoming} incoming</p>

      <section className="reach-section">
        <h3>AUTHORED REACH</h3>
        <div className="reach-grid">
          <div><span>Upstream</span><strong>{record.upstream}</strong></div>
          <div><span>Downstream</span><strong>{record.downstream}</strong></div>
        </div>
      </section>

      <section className="relationships-section">
        <h3>RELATIONSHIPS · {record.relationships.length}</h3>
        <div className="relationship-list">
          {record.relationships.map((relationship) => (
            <button
              key={`${record.id}-${relationship.id}-${relationship.direction}`}
              onClick={() => {
                const target = passports[relationship.id]
                if (target) onSelect(target)
              }}
              type="button"
            >
              <span className={`direction direction-${relationship.direction.toLowerCase()}`}>
                {relationship.direction === 'IN' ? '← IN' : relationship.direction === 'OUT' ? 'OUT →' : 'STEP'}
              </span>
              <span><strong>{relationship.name}</strong><small>{relationship.detail}</small></span>
            </button>
          ))}
        </div>
      </section>
    </aside>
  )
}

function HelpPanel({ onClose }: { onClose: () => void }) {
  return (
    <aside aria-label="Prototype help" className="help-panel">
      <header>
        <div><span className="panel-kicker">FIELD GUIDE</span><h2>Read the semantic map</h2></div>
        <button aria-label="Close help" className="icon-button" onClick={onClose} type="button">×</button>
      </header>
      <dl>
        <div><dt>PATH</dt><dd>Trace the authored Buyers → Payment Rail journey and dim unrelated context.</dd></div>
        <div><dt>MAP</dt><dd>Restore the complete architecture or sequence.</dd></div>
        <div><dt>LENS</dt><dd>Emphasize the checkout trust zone or one sequence step.</dd></div>
        <div><dt>Passport</dt><dd>Select a node, relationship, participant, or message to inspect its semantics.</dd></div>
        <div><dt>Radar</dt><dd>Use the minimap or message strip to retain orientation.</dd></div>
      </dl>
      <p>This is a visual and interaction PoC. Layout and sample data are intentionally static.</p>
    </aside>
  )
}

export default function App() {
  const [tab, setTab] = useState<DiagramTab>('architecture')
  const [mode, setMode] = useState<DiagramMode>('map')
  const [selection, setSelection] = useState<PassportRecord | null>(passports['checkout-api'])
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [copied, setCopied] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)

  const selectTab = (next: DiagramTab) => {
    setTab(next)
    setMode('map')
    setCopied(false)
    setSelection(next === 'architecture' ? passports['checkout-api'] : passports.m2)
  }

  const copyLink = useCallback(async () => {
    if (!selection) return
    const url = new URL(window.location.href)
    url.hash = new URLSearchParams({ tab, mode, selected: selection.id }).toString()
    await navigator.clipboard.writeText(url.toString())
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }, [mode, selection, tab])

  const toggleFullscreen = async () => {
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    } else {
      await document.documentElement.requestFullscreen()
    }
  }

  return (
    <div className="app" data-theme={theme}>
      <a className="skip-link" href="#diagram">Skip to diagram</a>
      <header className="app-header">
        <div className="brand-lockup">
          <span aria-hidden="true" className="brand-mark"><i /><i /><i /></span>
          <div>
            <span className="brand-eyebrow">ONETOOL · SEMANTIC ATLAS</span>
            <strong>Checkout Platform — Baseline</strong>
          </div>
        </div>

        <nav aria-label="Diagram type" className="diagram-tabs">
          <button aria-pressed={tab === 'architecture'} onClick={() => selectTab('architecture')} type="button">
            <span aria-hidden="true">⌘</span> Architecture
          </button>
          <button aria-pressed={tab === 'sequence'} onClick={() => selectTab('sequence')} type="button">
            <span aria-hidden="true">⇥</span> Sequence
          </button>
        </nav>

        <div className="header-actions">
          <span className="prototype-badge"><i /> LIVE POC</span>
          <button aria-label="Open field guide" className="icon-button" onClick={() => setHelpOpen((value) => !value)} type="button">?</button>
          <button
            aria-label={`Use ${theme === 'light' ? 'dark' : 'light'} theme`}
            className="icon-button"
            onClick={() => setTheme((value) => value === 'light' ? 'dark' : 'light')}
            type="button"
          >
            {theme === 'light' ? '◐' : '○'}
          </button>
          <button aria-label="Toggle full screen" className="icon-button" onClick={() => void toggleFullscreen()} type="button">↗</button>
        </div>
      </header>

      <main data-inspector={selection ? 'true' : 'false'} id="diagram">
        {tab === 'architecture' ? (
          <ArchitectureCanvas
            mode={mode}
            onModeChange={setMode}
            onSelect={setSelection}
            selectedId={selection?.id}
          />
        ) : (
          <SequenceCanvas
            mode={mode}
            onModeChange={setMode}
            onSelect={setSelection}
            selectedId={selection?.id}
          />
        )}
        {selection ? (
          <Passport
            copied={copied}
            onClose={() => setSelection(null)}
            onCopy={() => void copyLink()}
            onSelect={setSelection}
            record={selection}
          />
        ) : null}
        {helpOpen ? <HelpPanel onClose={() => setHelpOpen(false)} /> : null}
      </main>

      <footer className="app-footer">
        <span><i className="status-dot" /> local prototype</span>
        <span>React Flow architecture · native / ZenUML sequence spike · OneTool semantic identity</span>
        <span>light / baseline / container</span>
      </footer>
    </div>
  )
}
