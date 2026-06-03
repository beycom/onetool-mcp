import { InfoIcon, PanelRightIcon, RefreshCwIcon, SettingsIcon } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type CSSProperties, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { DisplayTimeline } from "./components/DisplayTimeline";
import { MessageActions, MessageInfo } from "./components/MessageRow";
import { PayloadRenderer } from "./components/PayloadRenderer";
import { Popover, PopoverPopup, PopoverTrigger } from "./components/ui/Popover";
import { DisplaySettingsProvider } from "./lib/displaySettings";
import type { DisplayStore } from "./lib/displayStore";
import { useDisplayStore } from "./lib/displayStore";
import { useMockDisplayStore } from "./lib/mockDisplayStore";

type ThemeChoice = "system" | "light" | "dark";
const PANEL_WIDTH_KEY = "onetool.display.sidePanelWidth";
const DEFAULT_PANEL_WIDTH = 560;
const MIN_PANEL_WIDTH = 380;
const MIN_MAIN_WIDTH = 360;

export function App() {
  const useMock = new URLSearchParams(window.location.search).has("mock") || !window.location.pathname.includes("/instances/");
  return useMock ? <MockDisplayApp /> : <LiveDisplayApp />;
}

function MockDisplayApp() {
  const store = useMockDisplayStore(window.location);
  return <DisplayAppShell store={store} label="mock artifact timeline" />;
}

function LiveDisplayApp() {
  const store = useDisplayStore(window.location);
  return <DisplayAppShell store={store} label={store.api.instanceId} />;
}

function DisplayAppShell({ store, label }: { store: DisplayStore; label: string }) {
  const [theme, setTheme] = useState<ThemeChoice>("system");
  const [panelOpen, setPanelOpen] = useState(true);
  const [panelMessageId, setPanelMessageId] = useState<string | null>(null);
  const [panelWidth, setPanelWidth] = useState(() => readStoredPanelWidth());
  const [wrapDiff, setWrapDiff] = useState(false);
  const [hideWhitespace, setHideWhitespace] = useState(true);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  const codeTheme = useMemo(() => resolveCodeTheme(theme), [theme]);
  const selectedPanelMessage = useMemo(() => {
    if (!panelMessageId) return null;
    return store.messages.find((message) => message.id === panelMessageId) ?? null;
  }, [panelMessageId, store.messages]);
  useEffect(() => {
    if (!selectedPanelMessage) return;
    store.loadPayload(selectedPanelMessage.id);
  }, [selectedPanelMessage, store]);
  const openPanelMessage = useCallback((id: string) => {
    setPanelOpen(true);
    setPanelMessageId(id);
    store.loadPayload(id);
  }, [store]);
  const panelLabel = panelOpen ? "Hide message inspector" : "Show message inspector";
  const shellStyle = panelOpen ? ({ "--side-panel-width": `${panelWidth}px` } as CSSProperties) : undefined;
  const startPanelResize = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = panelWidth;
    const maxWidth = Math.max(MIN_PANEL_WIDTH, window.innerWidth - MIN_MAIN_WIDTH);
    const onMove = (moveEvent: PointerEvent) => {
      const nextWidth = clamp(startWidth + startX - moveEvent.clientX, MIN_PANEL_WIDTH, maxWidth);
      setPanelWidth(nextWidth);
      window.localStorage.setItem(PANEL_WIDTH_KEY, String(nextWidth));
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp, { once: true });
  }, [panelWidth]);
  return (
    <DisplaySettingsProvider value={{ wrapDiff, hideWhitespace, codeTheme }}>
      <main className={`app-shell${panelOpen ? " panel-open" : ""}${wrapDiff ? " diff-wrap" : ""}${hideWhitespace ? " hide-whitespace" : ""}`} style={shellStyle}>
        <div className="main-column">
          <header className="topbar">
            <div>
              <h1>OneTool Display</h1>
              <p>{label}</p>
            </div>
            <div className="topbar-actions">
              <button type="button" className="icon-button" onClick={() => void store.refresh()} aria-label="Refresh">
                <RefreshCwIcon size={16} />
              </button>
              <Popover>
                <PopoverTrigger className="icon-button" aria-label="Open settings" title="Open settings">
                  <SettingsIcon size={16} />
                </PopoverTrigger>
                <PopoverPopup>
                  <div className="settings-popover" aria-label="Display settings">
                    <SettingsRow title="Theme" description="Choose how Display looks across the app.">
                      <select value={theme} onChange={(event) => setTheme(event.target.value as ThemeChoice)} aria-label="Theme">
                        <option value="system">System</option>
                        <option value="light">Light</option>
                        <option value="dark">Dark</option>
                      </select>
                    </SettingsRow>
                    <SettingsRow title="Diff line wrapping" description="Set the default wrap state when diff and raw code panels open.">
                      <input type="checkbox" checked={wrapDiff} onChange={(event) => setWrapDiff(event.target.checked)} aria-label="Diff line wrapping" />
                    </SettingsRow>
                    <SettingsRow title="Hide whitespace changes" description="Reserved for diff renderers that expose whitespace filtering.">
                      <input type="checkbox" checked={hideWhitespace} onChange={(event) => setHideWhitespace(event.target.checked)} aria-label="Hide whitespace changes" />
                    </SettingsRow>
                  </div>
                </PopoverPopup>
              </Popover>
              <button type="button" className="icon-button" onClick={() => setPanelOpen((open) => !open)} aria-label={panelLabel} title={panelLabel}>
                <PanelRightIcon size={16} />
              </button>
            </div>
          </header>
          {store.error ? <div className="error-banner">{store.error}</div> : null}
          <section className="timeline-shell" aria-label="Display timeline">
            <DisplayTimeline store={store} onOpenPanel={openPanelMessage} />
          </section>
        </div>
        {panelOpen ? (
          <>
          <div className="panel-resizer" role="separator" aria-label="Resize message inspector" aria-orientation="vertical" onPointerDown={startPanelResize} />
          <aside className="right-panel" aria-label="Display message inspector">
            <section className="inspector-section" aria-label="Selected message content">
              {selectedPanelMessage ? (
                <>
                  <div className="inspector-header">
                    <div className="inspector-title">
                      <span className={`kind kind-${selectedPanelMessage.kind}`}>{selectedPanelMessage.kind}</span>
                      <strong>{selectedPanelMessage.title || selectedPanelMessage.summary || selectedPanelMessage.id}</strong>
                    </div>
                    <div className="inspector-actions">
                      <MessageActions api={store.api} message={selectedPanelMessage} payload={store.payloadById.get(selectedPanelMessage.id)} />
                      <Popover>
                        <PopoverTrigger className="icon-button row-action" aria-label="Show message info" title="Message info">
                          <InfoIcon size={14} />
                        </PopoverTrigger>
                        <PopoverPopup>
                          <MessageInfo message={selectedPanelMessage} />
                        </PopoverPopup>
                      </Popover>
                    </div>
                  </div>
                  <div className="inspector-payload">
                    <PayloadRenderer api={store.api} message={selectedPanelMessage} payload={store.payloadById.get(selectedPanelMessage.id)} />
                  </div>
                </>
              ) : (
                <div className="inspector-empty">
                  <PanelRightIcon size={18} />
                  <p>Open a message in the side panel.</p>
                </div>
              )}
            </section>
          </aside>
          </>
        ) : null}
      </main>
    </DisplaySettingsProvider>
  );
}

function SettingsRow({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <div className="settings-row">
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      <div className="settings-control">{children}</div>
    </div>
  );
}

function resolveCodeTheme(theme: ThemeChoice): "light" | "dark" {
  if (theme === "light" || theme === "dark") return theme;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function readStoredPanelWidth(): number {
  const value = Number(window.localStorage.getItem(PANEL_WIDTH_KEY));
  return Number.isFinite(value) ? clamp(value, MIN_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, window.innerWidth - MIN_MAIN_WIDTH)) : DEFAULT_PANEL_WIDTH;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
