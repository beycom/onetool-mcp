export interface AdminInstance {
  identity: string;
  short_identity: string;
  base_url: string;
  cwd: string;
  started_at: string;
  api_version: number;
  status: "connected" | "disconnected";
  display: {
    status: string;
    mcp_instance_id: string;
    message_count: number;
    started_at: string;
    updated_at: string;
  };
  discovered_at: string;
  updated_at: string;
}
