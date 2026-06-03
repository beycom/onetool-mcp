import { AlertCircleIcon, BracesIcon, CalendarClockIcon, CheckIcon, CopyIcon, EllipsisIcon, ExternalLinkIcon, FileTextIcon, FolderTreeIcon, PanelRightOpenIcon } from "lucide-react";
import { memo, useCallback, type ReactNode, useState } from "react";
import type { DisplayApi } from "../api/displayApi";
import type { MessageMetadata, PayloadView } from "../types";
import { PayloadRenderer } from "./PayloadRenderer";
import { RenderErrorBoundary } from "./RenderErrorBoundary";
import { Popover, PopoverPopup, PopoverTrigger } from "./ui/Popover";

export const MessageRow = memo(function MessageRow({
  api,
  message,
  selected,
  payload,
  onOpenPanel,
  rich = true,
  onToggleRich,
  expanded = false,
  actionLayout = "timeline",
  extraActions,
}: {
  api: DisplayApi;
  message: MessageMetadata;
  selected: boolean;
  payload: PayloadView | undefined;
  onOpenPanel?: (id: string) => void;
  rich?: boolean;
  onToggleRich?: () => void;
  expanded?: boolean;
  actionLayout?: "timeline" | "inspector";
  extraActions?: ReactNode;
}) {
  return (
    <article className={`${selected ? "message-row selected" : "message-row"}${expanded ? " message-row-expanded" : ""}`} data-message-id={message.id}>
      <div className="message-toolbar">
        <div className="message-actions">
          <MessageActions
            api={api}
            message={message}
            payload={payload}
            onOpenPanel={onOpenPanel}
            rich={rich}
            onToggleRich={onToggleRich}
            layout={actionLayout}
          />
          {extraActions}
        </div>
      </div>
      <FileMessageHeader message={message} />
      <div className="preview-wrap">
        <div className="payload-panel">
          <RenderErrorBoundary label={message.id}>
            <PayloadRenderer api={api} message={message} payload={payload} rich={rich} />
          </RenderErrorBoundary>
        </div>
      </div>
      <footer className="message-meta">
        <MessageHeaderMeta message={message} />
        <span className="message-id" title={message.id}>{compactMessageId(message.id)}</span>
      </footer>
    </article>
  );
});

function FileMessageHeader({ message }: { message: MessageMetadata }) {
  const label = fileHeaderLabel(message);
  if (!label) return null;
  return (
    <header className="file-message-header" title={payloadPathLabel(message) ?? label}>
      <FileTextIcon size={14} />
      <span>{label}</span>
    </header>
  );
}

export function MessageActions({
  api,
  message,
  payload,
  onOpenPanel,
  rich,
  onToggleRich,
  layout,
}: {
  api: DisplayApi;
  message: MessageMetadata;
  payload: PayloadView | undefined;
  onOpenPanel?: (id: string) => void;
  rich: boolean;
  onToggleRich?: () => void;
  layout: "timeline" | "inspector";
}) {
  const filePath = actionPath(message);
  const openButton = filePath ? <OpenFileButton api={api} path={filePath} /> : null;
  const panelButton = onOpenPanel ? (
    <button type="button" className="icon-button row-action" onClick={() => onOpenPanel(message.id)} aria-label="Open message in side panel" title="Open in side panel">
      <PanelRightOpenIcon size={14} />
    </button>
  ) : null;
  if (layout === "inspector") {
    return (
      <>
        <MessageActionMenu api={api} message={message} payload={payload} rich={rich} onToggleRich={onToggleRich} />
        {openButton}
      </>
    );
  }
  return (
    <>
      <CopyMessageButton api={api} message={message} payload={payload} kind="content" />
      {panelButton}
      {openButton}
    </>
  );
}

function MessageActionMenu({
  api,
  message,
  payload,
  rich,
  onToggleRich,
}: {
  api: DisplayApi;
  message: MessageMetadata;
  payload: PayloadView | undefined;
  rich: boolean;
  onToggleRich?: () => void;
}) {
  const pathLabel = payloadPathLabel(message);
  const copyContent = useCopyMessageAction({ api, message, payload, kind: "content" });
  const copyPath = useCopyMessageAction({ api, message, payload, kind: "path" });
  return (
    <Popover>
      <PopoverTrigger className="icon-button row-action" aria-label="Open message actions" title="Message actions">
        <EllipsisIcon size={14} />
      </PopoverTrigger>
      <PopoverPopup sideOffset={4}>
        <div className="message-action-menu" aria-label="Message actions">
          {pathLabel ? (
            <button type="button" className="message-action-menu-item" onClick={copyPath.copy}>
              {copyPath.copied ? <CheckIcon size={16} /> : <FolderTreeIcon size={16} />}
              <span>{copyPath.copied ? "Copied path" : "Copy path"}</span>
            </button>
          ) : null}
          <button type="button" className="message-action-menu-item" onClick={copyContent.copy}>
            {copyContent.copied ? <CheckIcon size={16} /> : <CopyIcon size={16} />}
            <span>{copyContent.copied ? "Copied file contents" : "Copy file contents"}</span>
          </button>
          {onToggleRich ? (
            <button type="button" className="message-action-menu-item" onClick={onToggleRich}>
              <BracesIcon size={16} />
              <span>{rich ? "Disable rich view" : "Enable rich view"}</span>
            </button>
          ) : null}
        </div>
      </PopoverPopup>
    </Popover>
  );
}

export function MessageHeaderMeta({ message }: { message: MessageMetadata }) {
  return (
    <>
      <span className="row-header-meta-item" title={message.created_at}>
        <CalendarClockIcon size={13} />
        <span>{formatTimestamp(message.created_at)}</span>
      </span>
    </>
  );
}

export function MessageInfo({ message }: { message: MessageMetadata }) {
  const pathLabel = payloadPathLabel(message);
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
      {pathLabel ? (
        <div>
          <dt>Path</dt>
          <dd title={pathLabel}>{pathLabel}</dd>
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
  const { copied, copy } = useCopyMessageAction({ api, message, payload, kind });
  const label = kind === "path" ? "Copy path" : "Copy content";
  return (
    <button type="button" className="icon-button row-action" onClick={copy} aria-label={copied ? `Copied ${kind}` : label} title={label}>
      {copied ? <CheckIcon size={14} /> : kind === "path" ? <FolderTreeIcon size={14} /> : <CopyIcon size={14} />}
    </button>
  );
}

function useCopyMessageAction({
  api,
  message,
  payload,
  kind,
}: {
  api: DisplayApi;
  message: MessageMetadata;
  payload: PayloadView | undefined;
  kind: "content" | "path";
}): { copied: boolean; copy: () => void } {
  const [copied, setCopied] = useState(false);
  const [fetchedPayload, setFetchedPayload] = useState<PayloadView | undefined>(undefined);
  const copy = useCallback(() => {
    const copyFromPayload = (view: PayloadView | undefined) => view?.preview?.text ?? stringifyPayload(view?.content) ?? message.summary ?? message.title ?? message.id;
    const textPromise = kind === "path"
      ? Promise.resolve(payloadPathLabel(message) ?? "")
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
  return { copied, copy };
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
  const label = status === "opened" ? "Opened" : status === "failed" ? "Open failed" : "Open file";
  return (
    <button type="button" className={`icon-button row-action row-open${status === "failed" ? " failed" : ""}`} onClick={open} aria-label={error ?? label} title={error ?? label}>
      {status === "failed" ? <AlertCircleIcon size={14} /> : <ExternalLinkIcon size={14} />}
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
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const hour = date.getHours().toString().padStart(2, "0");
  const minute = date.getMinutes().toString().padStart(2, "0");
  const day = date.getDate().toString().padStart(2, "0");
  return `${hour}:${minute}, ${day}-${months[date.getMonth()]}`;
}

function fileName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? path;
}

function compactMessageId(id: string): string {
  return id;
}

function actionPath(message: MessageMetadata): string | null {
  return message.payload.path ?? null;
}

function fileHeaderLabel(message: MessageMetadata): string | null {
  if (message.kind === "file" || message.kind === "image") {
    return message.payload.path ? fileName(message.payload.path) : null;
  }
  if (message.kind === "file_diff") {
    return payloadPathDisplay(message);
  }
  return null;
}

function payloadPathLabel(message: MessageMetadata): string | null {
  if (message.payload.path) return message.payload.path;
  if (message.payload.old_path && message.payload.new_path) {
    return `${message.payload.old_path} -> ${message.payload.new_path}`;
  }
  return null;
}

function payloadPathDisplay(message: MessageMetadata): string {
  if (message.payload.path) return fileName(message.payload.path);
  if (message.payload.old_path && message.payload.new_path) {
    return `${fileName(message.payload.old_path)} -> ${fileName(message.payload.new_path)}`;
  }
  return "";
}

function stringifyPayload(content: unknown): string | null {
  if (typeof content === "string") return content;
  if (content === undefined || content === null) return null;
  return JSON.stringify(content, null, 2);
}
