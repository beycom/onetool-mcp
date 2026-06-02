import type { DisplayEvent, MessageList, MessageRead, PayloadView } from "../types";

export class DisplayApi {
  readonly instanceId: string;
  readonly token: string;

  constructor(location: Location) {
    const parts = location.pathname.split("/").filter(Boolean);
    this.instanceId = parts[1] ?? "";
    this.token = new URLSearchParams(location.search).get("token") ?? "";
  }

  async list(limit = 300): Promise<MessageList> {
    return this.get(`/messages?limit=${limit}`);
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
    return `/api/instances/${this.instanceId}${path}${separator}token=${encodeURIComponent(this.token)}`;
  }
}
