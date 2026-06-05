import type { AdminInstance } from "./adminTypes";

export class AdminApi {
  readonly adminOrigin: string;

  constructor(location: Location) {
    this.adminOrigin = location.origin;
  }

  async scan(): Promise<AdminInstance[]> {
    const response = await fetch("/api/admin/scan", { method: "POST" });
    if (!response.ok) throw new Error(`Admin API ${response.status}`);
    const payload = (await response.json()) as { instances: AdminInstance[] };
    return payload.instances;
  }

  async instances(): Promise<AdminInstance[]> {
    const response = await fetch("/api/admin/instances");
    if (!response.ok) throw new Error(`Admin API ${response.status}`);
    const payload = (await response.json()) as { instances: AdminInstance[] };
    return payload.instances;
  }
}
