# Changelog

## 4.0.0rc1, local candidate

OneTool is now a YAML-configured MCP gateway using FastMCP CodeMode. Native search, schemas and Python execution replace the owned executor and tool catalog. Status, reload/restart, private large-result files and operational logs cover local operation.

V4 removes bundled packs, extension loading, direct HTTP ingress, persistent Python sessions, dashboards, snippets, aliases and the old config/API. Run a pinned older release as an ordinary upstream for old pack workflows.

This candidate is not published. Real OAuth login, a week of owner dogfooding, main cutover and publishing remain open.

The earlier changelog and implementation are preserved in the local `archive/pre-v4-main` branch. Read them there; V4 does not migrate or detect old configuration.
