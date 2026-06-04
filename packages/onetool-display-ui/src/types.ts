export type DisplayKind =
  | "text"
  | "markdown"
  | "code"
  | "file"
  | "diff"
  | "file_diff"
  | "image"
  | "json"
  | "mermaid"
  | "yaml"
  | "table";

export type PayloadMode = "inline" | "file" | "file_diff";

export interface PayloadReference {
  mode: PayloadMode;
  size_bytes: number;
  path?: string | null;
  old_path?: string | null;
  new_path?: string | null;
  mime_type?: string | null;
  language?: string | null;
}

export interface MessageMetadata {
  id: string;
  kind: DisplayKind;
  metadata: Record<string, string>;
  preview_lines?: number | null;
  created_at: string;
  updated_at: string;
  payload: PayloadReference;
  status: "ready" | "preview_unavailable";
}

export interface BoundedPreview {
  text: string;
  truncated: boolean;
  size_bytes: number;
  limit_bytes: number;
}

export interface MessageRead {
  metadata: MessageMetadata;
  preview?: BoundedPreview | null;
}

export interface PayloadView extends MessageRead {
  content?: unknown;
  image_url?: string | null;
  file_url?: string | null;
  open_url?: string | null;
}

export interface FilePreview {
  path: string;
  text: string;
  truncated: boolean;
  size_bytes: number;
  limit_bytes: number;
}

export interface MessageList {
  items: MessageMetadata[];
  total: number;
  offset: number;
  limit: number;
}

export interface DisplayEvent {
  type: "message" | "focus";
  id: string;
}
