export interface AdminInstance {
  identity: string;
  short_identity: string;
  base_url: string;
  cwd: string;
  started_at: string;
  api_version: number;
  status: "connected" | "disconnected";
  meta: {
    identity?: string;
    short_identity?: string;
    name?: string;
    description?: string;
    cwd?: string;
    config_path?: string | null;
    config_dir?: string | null;
    direct_base_url?: string | null;
    direct_port?: number | null;
    started_at?: string;
    updated_at?: string | null;
  };
  heartbeat_seconds: number;
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
