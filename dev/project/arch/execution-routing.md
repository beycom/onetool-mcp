# Execution Routing

Tools are routed to one of three executors based on their type.

## Executor Types

| Executor | When | Example |
|----------|------|---------|
| **SimpleExecutor** | Bundled/extension tools with no heavy deps | `brave.search`, `file.read` |
| **WorkerPool** | User extension tools with PEP 723 inline script metadata | A standalone extension declaring its own dependencies |
| **ProxyManager** | External MCP servers defined in config | `github.get_file_contents` |

## Sequence Diagram

```mermaid
sequenceDiagram
    participant R as runner.py
    participant L as tool_loader
    participant S as SimpleExecutor
    participant W as WorkerPool
    participant P as ProxyManager
    participant T as Tool Module
    participant X as Subprocess
    participant E as External MCP

    R->>L: load_tools(registry)
    L->>L: Scan bundled ottools/*.py
    L->>L: Scan config tools_dir globs
    L->>L: Detect PEP 723 metadata
    L-->>R: LoadedTools

    alt Bundled / in-process Extension Tool
        Note over R,T: Trusted code loaded into the MCP process
        R->>S: execute(code, namespace)
        S->>T: Direct function call
        T-->>S: Result
        S-->>R: Serialised result

    else PEP 723 Worker Tool
        Note over R,X: Has inline script deps
        R->>W: execute(tool, kwargs)
        W->>W: Get or create worker process
        W->>X: Send request via stdio
        X->>X: Import deps & run function
        X-->>W: Result via stdio
        W-->>R: Serialised result

    else External MCP Server
        Note over R,E: Defined in servers.yaml
        R->>P: call_tool(server, tool, args)
        P->>P: Get connected client
        P->>E: MCP tool/call request
        E-->>P: MCP response
        P-->>R: Parsed result
    end
```


## Key Files

| File | Role |
|------|------|
| `src/ot/executor/tool_loader.py` | Discovers tools, detects PEP 723, builds LoadedTools |
| `src/ot/executor/simple.py` | In-process execution (fast, no isolation) |
| `src/ot/executor/worker_pool.py` | Subprocess pool for isolated execution |
| `src/ot/proxy/manager.py` | Routes calls to external MCP servers |
| `src/ot/executor/pack_proxy.py` | PackProxy, McpProxyPack, WorkerPackProxy |
