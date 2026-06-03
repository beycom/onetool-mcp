import { AlertCircleIcon, CheckIcon, ClockIcon, CopyIcon, ExternalLinkIcon, FileTextIcon, PanelRightOpenIcon, ScrollTextIcon } from "lucide-react";
import { memo, useCallback, useState } from "react";
import type { DisplayApi } from "../api/displayApi";
import type { MessageMetadata, PayloadView } from "../types";
import { PayloadRenderer } from "./PayloadRenderer";

export const MessageRow = memo(function MessageRow({
  api,
  message,
  expanded,
  selected,
  payload,
  onToggle,
  onOpenPanel,
}: {
  api: DisplayApi;
  message: MessageMetadata;
  expanded: boolean;
  selected: boolean;
  payload: PayloadView | undefined;
  onToggle: (id: string) => void;
  onOpenPanel: (id: string) => void;
}) {
  return (
    <article className={selected ? "message-row selected" : "message-row"} data-message-id={message.id}>
      <div className="message-toolbar">
        <div className="message-title">
          <span className={`kind kind-${message.kind}`}>{message.kind}</span>
          <strong>{message.title || message.summary || message.id}</strong>
        </div>
        <div className="message-actions">
          <MessageActions api={api} message={message} payload={payload} onOpenPanel={onOpenPanel} />
        </div>
      </div>
      <div className={`preview-wrap${expanded ? "" : " is-collapsed"}${message.preview_lines && message.preview_lines > 5 ? " truncated" : ""}`}>
        <div className="payload-panel">
          {expanded || payload ? <PayloadRenderer api={api} message={message} payload={payload} /> : <CollapsedPreview message={message} />}
        </div>
        <button type="button" className="preview-toggle" onClick={() => onToggle(message.id)} aria-expanded={expanded}>
          {expanded ? "collapse" : "expand"}
        </button>
      </div>
      <footer className="message-meta">
        <MessageHeaderMeta message={message} />
        <span className="message-id" title={message.id}>{message.id}</span>
      </footer>
    </article>
  );
});

function CollapsedPreview({ message }: { message: MessageMetadata }) {
  return (
    <pre className="raw-block preview-placeholder">
      {message.summary || message.title || message.id}
    </pre>
  );
}

export function MessageActions({
  api,
  message,
  payload,
  onOpenPanel,
}: {
  api: DisplayApi;
  message: MessageMetadata;
  payload: PayloadView | undefined;
  onOpenPanel?: (id: string) => void;
}) {
  return (
    <>
      <CopyMessageButton api={api} message={message} payload={payload} kind="content" />
      {message.payload.path ? <CopyMessageButton api={api} message={message} payload={payload} kind="path" /> : null}
      {message.payload.path ? <OpenFileButton api={api} path={message.payload.path} /> : null}
      {onOpenPanel ? (
          <button type="button" className="icon-button row-action" onClick={() => onOpenPanel(message.id)} aria-label="Open message in side panel" title="Open in side panel">
            <PanelRightOpenIcon size={14} />
          </button>
      ) : null}
    </>
  );
}

export function MessageHeaderMeta({ message }: { message: MessageMetadata }) {
  return (
    <>
      <span className="row-header-meta-item" title="Message size">
        <ScrollTextIcon size={13} />
        <span>{formatBytes(message.payload.size_bytes)}</span>
      </span>
      <span className="row-header-meta-item" title="Preview line count">
        <span>{message.preview_lines ?? 0} lines</span>
      </span>
      <span className="row-header-meta-item" title={message.created_at}>
        <ClockIcon size={13} />
        <span>{formatTimestamp(message.created_at)}</span>
      </span>
      {message.payload.path ? (
        <span className="row-header-meta-item row-path" title={message.payload.path}>
          <FileTextIcon size={13} />
          <span>{message.payload.path}</span>
        </span>
      ) : null}
    </>
  );
}

export function MessageInfo({ message }: { message: MessageMetadata }) {
  return (
    <dl className="message-info">
      <div>
        <dt>Kind</dt>
        <dd>{message.kind}</dd>
      </div>
      <div>
        <dt>Size</dt>
        <dd>{formatBytes(message.payload.size_bytes)}</dd>
      </div>
      <div>
        <dt>Created</dt>
        <dd>{formatTimestamp(message.created_at)}</dd>
      </div>
      {message.payload.path ? (
        <div>
          <dt>Path</dt>
          <dd title={message.payload.path}>{message.payload.path}</dd>
        </div>
      ) : null}
      <div>
        <dt>ID</dt>
        <dd title={message.id}>{message.id}</dd>
      </div>
    </dl>
  );
}

export function CopyMessageButton({
  api,
  message,
  payload,
  kind,
}: {
  api: DisplayApi;
  message: MessageMetadata;
  payload: PayloadView | undefined;
  kind: "content" | "path";
}) {
  const [copied, setCopied] = useState(false);
  const [fetchedPayload, setFetchedPayload] = useState<PayloadView | undefined>(undefined);
  const copy = useCallback(() => {
    const copyFromPayload = (view: PayloadView | undefined) => view?.preview?.text ?? stringifyPayload(view?.content) ?? message.summary ?? message.title ?? message.id;
    const textPromise = kind === "path"
      ? Promise.resolve(message.payload.path ?? "")
      : (payload ?? fetchedPayload
        ? Promise.resolve(payload ?? fetchedPayload)
        : api.payload(message.id).then((view) => {
          setFetchedPayload(view);
          return view;
        })).then(copyFromPayload);
    void textPromise.then((text) => navigator.clipboard?.writeText(text)).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    });
  }, [api, fetchedPayload, kind, message, payload]);
  const label = kind === "path" ? "Copy path" : "Copy content";
  return (
    <button type="button" className="icon-button row-action" onClick={copy} aria-label={copied ? `Copied ${kind}` : label} title={label}>
      {copied ? <CheckIcon size={14} /> : kind === "path" ? <FileTextIcon size={14} /> : <CopyIcon size={14} />}
    </button>
  );
}

export function OpenFileButton({ api, path }: { api: DisplayApi; path: string }) {
  const [status, setStatus] = useState<"idle" | "opened" | "failed">("idle");
  const [error, setError] = useState<string | null>(null);
  const open = useCallback(() => {
    setStatus("idle");
    setError(null);
    void api.open(path).then((result) => {
      setStatus(result.opened ? "opened" : "failed");
      setError(result.opened ? null : `Open unavailable for ${result.path}`);
    }).catch((err: unknown) => {
      setStatus("failed");
      setError(err instanceof Error ? err.message : String(err));
    });
  }, [api, path]);
  const label = status === "opened" ? "Opened" : status === "failed" ? "Open failed" : "Open";
  return (
    <button type="button" className={`text-button row-open${status === "failed" ? " failed" : ""}`} onClick={open} aria-label={error ?? "Open file"} title={error ?? "Open file"}>
      {status === "failed" ? <AlertCircleIcon size={14} /> : <ExternalLinkIcon size={14} />}
      {label}
    </button>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function stringifyPayload(content: unknown): string | null {
  if (typeof content === "string") return content;
  if (content === undefined || content === null) return null;
  return JSON.stringify(content, null, 2);
}
