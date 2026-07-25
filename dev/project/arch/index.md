# Architecture Overview

OneTool is a single MCP server that exposes configured tool packs through one `run` endpoint. Instead of LLMs reading verbose tool schemas (~3K-30K tokens per server), agents write Python code:

```python
__onetool brave.search(query="react docs")
```

This delivers ~97% token savings and eliminates context rot.

## Architecture Diagram

```mermaid
graph TD
    C[Client - LLM] -->|"__onetool brave.search(...)"| M[MCP Protocol]
    M -->|"single run tool"| S[server.py - FastMCP]

    S --> R[runner.py]

    R --> FP[fence_processor<br/>Strip trigger prefix & fences]
    R --> VA[validator.py<br/>AST security checks]
    R --> TL[tool_loader<br/>Discover & load modules]
    R --> PP[pack_proxy<br/>Build namespaces]

    TL --> REG[registry/<br/>AST-based metadata scan]

    R --> SE[SimpleExecutor<br/>Host-process - fast]
    R --> PM[ProxyManager<br/>External MCP servers]

    SE --> BT[Built-in and Extension Tools<br/>brave, file, custom packs, ...]
    PM --> ET[External Servers<br/>github, devtools, ...]

    BT --> SER[Result Serialisation<br/>JSON / YAML / raw]
    ET --> SER

    SER --> RESP[MCP Response]

    style C fill:#e1f5fe
    style S fill:#f3e5f5
    style R fill:#fff3e0
    style SE fill:#e8f5e9
    style PM fill:#e8f5e9
    style SER fill:#fce4ec
```

## Project Structure

```
src/
  ot/                        # Core framework
    server.py                #   FastMCP server, single "run" tool
    tools.py                 #   Inter-tool API (call_tool, get_pack)
    meta.py                  #   Path resolution (resolve_ot_path)
    decorators.py            #   @tool decorator
    config/                  #   YAML config loading & Pydantic models
    executor/                #   Python code execution engine
      runner.py              #     Unified command execution
      validator.py           #     AST security validation
      tool_loader.py         #     Tool discovery & loading
      pack_proxy.py          #     Namespace building & proxies
      param_resolver.py      #     Keyword argument resolution
      fence_processor.py     #     Strip prefixes & code fences
      simple.py              #     In-process executor
      linter.py              #     Code linting
    registry/                #   Tool metadata scanning (AST-based)
    shortcuts/               #   Aliases & snippets
    proxy/                   #   External MCP server proxy
    logging/                 #   Structured logging (LogSpan, LogEntry)
    stats/                   #   Execution statistics (JSONL)
    utils/                   #   Format, sanitise, validation helpers

  ottools/                  # Base tool packs
    ot_forge.py              #   Extension scaffolding and validation
    ot_image.py              #   Image loading, inspection, generation, lifecycle
    ot_llm.py                #   LLM-powered transforms
    ot_secrets.py            #   Secret management
    ot_servers.py            #   External MCP server management
    ot_timer.py              #   Named stopwatch timers
    server.py                #   MCP server metadata/resources
    skills.py                #   Skills loading and lookup

  otdev/tools/              # Optional [dev] tool packs
    context7.py              #   Library documentation lookup
    db.py                    #   Database operations
    diagram.py               #   Diagram generation
    ripgrep.py               #   Fast code search
    webfetch.py              #   Web page fetching

  otutil/tools/             # Optional [util] tool packs
    brave.py                 #   Brave web/news/image/video search
    convert.py               #   Document conversion
    excel.py                 #   Excel file handling
    file.py                  #   Filesystem operations
    ground.py                #   Gemini grounding search
    mem.py                   #   Persistent memory tools

  onetool/                   # MCP server CLI (onetool.cli:cli)
```

## Deep Dives

| Document | Topic |
|----------|-------|
| [Core Concepts](core-concepts.md) | Packs, aliases, snippets, namespaces |
| [Request Pipeline](request-pipeline.md) | End-to-end request processing (sequence diagram) |
| [Execution Routing](execution-routing.md) | How tools are dispatched to executors (sequence diagram) |
| [Registry System](registry-system.md) | AST-based tool discovery (sequence diagram) |
| [Proxy Flow](proxy-flow.md) | External MCP server communication (sequence diagram) |
| [Security Model](security-model.md) | Four-layer defence, validation, sanitisation |
| [Configuration Architecture](configuration-architecture.md) | Config files, resolution, output formatting |
