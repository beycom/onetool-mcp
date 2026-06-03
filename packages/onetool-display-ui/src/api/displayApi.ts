import type { DisplayEvent, FilePreview, MessageList, MessageRead, PayloadView } from "../types";

declare global {
  interface Window {
    __ONETOOL_DISPLAY_BOOTSTRAP__?: {
      instanceId: string;
      token: string;
    };
  }
}

export class DisplayApi {
  readonly instanceId: string;
  readonly token: string;

  constructor(location: Location) {
    const parts = location.pathname.split("/").filter(Boolean);
    const bootstrap = window.__ONETOOL_DISPLAY_BOOTSTRAP__;
    this.instanceId = bootstrap?.instanceId ?? parts[1] ?? "";
    this.token = bootstrap?.token ?? new URLSearchParams(location.search).get("token") ?? "";
  }

  async list(limit = 300, options: { tail?: boolean; offset?: number } = {}): Promise<MessageList> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (options.offset) params.set("offset", String(options.offset));
    if (options.tail) params.set("tail", "true");
    return this.get(`/messages?${params.toString()}`);
  }

  async read(id: string): Promise<MessageRead> {
    return this.get(`/messages/${encodeURIComponent(id)}`);
  }

  async payload(id: string): Promise<PayloadView> {
    return this.get(`/messages/${encodeURIComponent(id)}/payload`);
  }

  async events(): Promise<DisplayEvent[]> {
    const response = await this.get<{ events: DisplayEvent[] }>("/events");
    return response.events;
  }

  async open(path: string): Promise<{ status: string; opened: boolean; path: string }> {
    return this.post("/open", { path });
  }

  async preview(path: string): Promise<FilePreview> {
    return this.get(`/preview?path=${encodeURIComponent(path)}`);
  }

  private async get<T>(path: string): Promise<T> {
    const response = await fetch(this.url(path));
    if (!response.ok) throw new Error(`Display API ${response.status}`);
    return (await response.json()) as T;
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(this.url(path), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`Display API ${response.status}`);
    return (await response.json()) as T;
  }

  private url(path: string): string {
    const separator = path.includes("?") ? "&" : "?";
    return `/api/display/instances/${this.instanceId}${path}${separator}token=${encodeURIComponent(this.token)}`;
  }
}
