import type { DisplayEvent, FilePreview, MessageList, MessageRead, PayloadView } from "./types";

export class DisplayApi {
  readonly instanceId: string;
  readonly adminOrigin: string;

  constructor(location: Location, instanceId: string) {
    this.adminOrigin = location.origin;
    this.instanceId = instanceId;
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
    return `/api/admin/instances/${encodeURIComponent(this.instanceId)}/display${path}`;
  }
}
