// ---------------------------------------------------------------------------
// FrameSource — payload for the "frame" kind
// ---------------------------------------------------------------------------

export type FrameSource =
  | { type: "inline"; html: string }
  | { type: "file"; path: string }
  | { type: "url"; url: string };

// ---------------------------------------------------------------------------
// PanelMessage — union of all content kinds pushed via panel.push()
// ---------------------------------------------------------------------------

export type MarkdownMessage = {
  kind: "markdown";
  id: string;
  text: string;
};

export type FrameMessage = {
  kind: "frame";
  id: string;
  source: FrameSource;
  heightPx?: number;
};

export type ImageMessage = {
  kind: "image";
  id: string;
  src: string;
  alt?: string;
};

export type JsonMessage = {
  kind: "json";
  id: string;
  data: unknown;
  label?: string;
  expanded?: number;
};

export type YamlMessage = {
  kind: "yaml";
  id: string;
  text: string;
  label?: string;
};

export type TableMessage = {
  kind: "table";
  id: string;
  rows: Record<string, unknown>[];
  columns?: string[];
};

export type DiffMessage = {
  kind: "diff";
  id: string;
  before: string;
  after: string;
  lang?: string;
  mode?: "split" | "unified";
};

export type TerminalMessage = {
  kind: "terminal";
  id: string;
  text: string;
  label?: string;
};

export type ClearMessage = {
  kind: "clear";
};

export type PanelMessage =
  | MarkdownMessage
  | FrameMessage
  | ImageMessage
  | JsonMessage
  | YamlMessage
  | TableMessage
  | DiffMessage
  | TerminalMessage;
