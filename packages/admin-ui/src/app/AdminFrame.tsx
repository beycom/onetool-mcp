import { SearchIcon, ServerIcon } from "lucide-react";
import { LiveDisplayApp, MockDisplayApp } from "../features/display/DisplayApp";
import type { AdminInstance } from "./adminTypes";

export function AdminFrame({
  instances,
  selected,
  error,
  onScan,
  onSelect,
}: {
  instances: AdminInstance[];
  selected: AdminInstance | null;
  error: string | null;
  onScan: () => Promise<void>;
  onSelect: (identity: string) => void;
}) {
  return (
    <div className="admin-layout">
      <aside className="instance-sidebar" aria-label="MCP instances">
        <div className="instance-toolbar">
          <h1>OneTool Admin</h1>
          <div className="instance-actions">
            <button type="button" className="icon-button" onClick={() => void onScan()} aria-label="Scan MCP instances" title="Scan MCP instances">
              <SearchIcon size={16} />
            </button>
          </div>
        </div>
        {error ? <div className="error-banner">{error}</div> : null}
        <div className="instance-list">
          {instances.map((instance) => (
            <button
              key={instance.identity}
              type="button"
              className={`instance-item${selected?.identity === instance.identity ? " active" : ""}`}
              onClick={() => onSelect(instance.identity)}
            >
              <ServerIcon size={15} />
              <span>{instanceLabel(instance)}</span>
              <small>{instance.status}</small>
            </button>
          ))}
        </div>
      </aside>
      <section className="admin-content">
        {selected ? <LiveDisplayApp instance={selected} /> : <MockDisplayApp />}
      </section>
    </div>
  );
}

function instanceLabel(instance: AdminInstance): string {
  const name = instance.meta?.name?.trim();
  if (name) return name;
  const cwdParts = instance.cwd.split("/").filter(Boolean);
  const cwdName = cwdParts[cwdParts.length - 1];
  return cwdName || instance.short_identity || instance.identity;
}
