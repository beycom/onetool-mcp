# Request Processing Pipeline

Every call flows through an eight-stage pipeline from client to response.

## Stages

1. **Input normalisation** - Remove trigger prefix (`__onetool`, `__ot`), markdown fences, and backticks
2. **Snippet expansion** - Expand `:name key=value` snippets into Python when the normalised command starts with `:`
3. **Validation** - AST-based security checks against allowlists
4. **Code preparation** - Parse Python, auto-wrap last expression as return
5. **Namespace building** - Load tool packs as proxy objects
6. **Execution** - Run code in sandboxed namespace via `exec()`
7. **Serialisation** - Convert result to JSON/YAML/raw string
8. **Statistics** - Record execution timing and metadata

## Sequence Diagram

```mermaid
sequenceDiagram
    participant C as Client (LLM)
    participant M as MCP Protocol
    participant S as server.py
    participant F as fence_processor
    participant V as validator
    participant R as runner.py
    participant L as tool_loader
    participant P as pack_proxy
    participant E as Executor
    participant T as Tool Function

    C->>M: run(command="__onetool brave.search(query='test')")
    M->>S: Handle tool call

    rect rgb(240, 248, 255)
        Note over S,F: Phase 1: Prepare Command
        S->>F: strip_fences(command)
        F-->>S: "brave.search(query='test')"
        S->>V: validate_python_code(code)
        V->>V: AST parse & check allowlists
        V-->>S: ValidationResult(ok=True)
    end

    rect rgb(245, 255, 245)
        Note over S,P: Phase 2: Build Namespace
        S->>R: execute_command(code, registry)
        R->>L: load_tools(registry)
        L->>L: Import tool modules (cached)
        L-->>R: LoadedTools(functions, packs)
        R->>P: build_namespace(loaded_tools)
        P-->>R: {brave: PackProxy, file: PackProxy, ...}
    end

    rect rgb(255, 248, 240)
        Note over R,T: Phase 3: Execute
        R->>R: prepare_code_for_exec(code)
        R->>E: exec(prepared_code, namespace)
        E->>P: namespace["brave"].search(query="test")
        P->>P: resolve & wrap with stats
        P->>T: brave.search(query="test")
        T->>T: HTTP call to Brave API
        T-->>P: {web: [{title: ...}]}
        P-->>E: result
        E-->>R: result
    end

    rect rgb(248, 245, 255)
        Note over R,S: Phase 4: Serialise
        R->>R: serialize_result(result, format="json")
        R-->>S: JSON string
        S->>S: Record stats
    end

    S-->>M: TextContent(json_string)
    M-->>C: MCP Response
```

## Key Files

| File | Role |
|------|------|
| `src/ot/server.py` | FastMCP server, `run()` entry point |
| `src/ot/executor/runner.py` | Orchestrates prepare + execute |
| `src/ot/executor/fence_processor.py` | Strips trigger prefixes, fences, and backticks |
| `src/ot/executor/validator.py` | AST-based security validation |
| `src/ot/executor/pack_proxy.py` | Builds dot-notation namespace |
| `src/ot/utils/format.py` | Result serialisation (JSON/YAML/raw) |
