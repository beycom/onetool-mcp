import { CheckIcon, ChevronDownIcon, ChevronRightIcon, ClockIcon, CopyIcon, ExternalLinkIcon, FileTextIcon, PanelRightOpenIcon, ScrollTextIcon } from "lucide-react";
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
      <div className="row-header">
        <button type="button" className="row-toggle" onClick={() => onToggle(message.id)} aria-expanded={expanded}>
          {expanded ? <ChevronDownIcon size={16} /> : <ChevronRightIcon size={16} />}
          <span className={`kind kind-${message.kind}`}>{message.kind}</span>
          <span className="row-copy">
            <strong>{message.title || message.summary || message.id}</strong>
            {message.summary && message.summary !== message.title ? <small>{message.summary}</small> : null}
            <MessageHeaderMeta message={message} />
          </span>
        </button>
        <div className="row-actions">
          <CopyMessageButton api={api} message={message} payload={payload} kind="content" />
          {message.payload.path ? <CopyMessageButton api={api} message={message} payload={payload} kind="path" /> : null}
          {message.payload.path ? <OpenFileButton api={api} path={message.payload.path} /> : null}
          <button type="button" className="icon-button row-action" onClick={() => onOpenPanel(message.id)} aria-label="Open message in side panel" title="Open in side panel">
            <PanelRightOpenIcon size={14} />
          </button>
        </div>
      </div>
      {expanded ? (
        <div className="payload-panel">
          <PayloadRenderer api={api} message={message} payload={payload} />
        </div>
      ) : null}
    </article>
  );
});

function MessageHeaderMeta({ message }: { message: MessageMetadata }) {
  return (
    <span className="row-header-meta">
      {message.payload.path ? (
        <span className="row-header-meta-item row-path" title={message.payload.path}>
          <FileTextIcon size={13} />
          <span>{message.payload.path}</span>
        </span>
      ) : null}
      <span className="row-header-meta-item" title="Message size">
        <ScrollTextIcon size={13} />
        <span>{formatBytes(message.payload.size_bytes)}</span>
      </span>
      <span className="row-header-meta-item" title={message.created_at}>
        <ClockIcon size={13} />
        <span>{formatTimestamp(message.created_at)}</span>
      </span>
    </span>
  );
}

function CopyMessageButton({
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
      {copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
    </button>
  );
}

function OpenFileButton({ api, path }: { api: DisplayApi; path: string }) {
  const [opened, setOpened] = useState(false);
  const open = useCallback(() => {
    void api.open(path).then((result) => setOpened(result.opened));
  }, [api, path]);
  return (
    <button type="button" className="text-button row-open" onClick={open} aria-label="Open file" title="Open file">
      <ExternalLinkIcon size={14} />
      {opened ? "Opened" : "Open"}
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
