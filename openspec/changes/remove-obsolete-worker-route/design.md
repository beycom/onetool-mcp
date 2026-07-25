## Context

Configured tools currently pass through a PEP 723 classifier. Files declaring
dependencies become worker proxies, while all other files are imported
in-process. Forge produces only in-process extensions, and the worker protocol
has no supported scaffold or consumer. Worker-specific type checks have spread
into discovery, diagnostics, CLI output, and docs generation.

## Goals / Non-Goals

**Goals:**

- Load all configured extensions through the existing importlib path.
- Remove subprocess routing, PEP 723 parsing, worker protocol state, and all
  worker-only branches and tests.
- Keep static discovery in the registry and runtime loading behavior intact.
- Make current specs and guidance describe one in-process extension model.

**Non-Goals:**

- Terminate arbitrary synchronous Python after a timeout.
- Install extension dependencies dynamically.
- Preserve a compatibility import or error stub for worker APIs.
- Change external MCP proxy execution.

## Decisions

1. **Use the existing in-process loader for every configured file.** It already
   provides pack registration, aliases, service registration, caching, and
   reload behavior. Keeping a classifier with one output would add no value.

2. **Delete `pep723.py` rather than rename it.** Its generic AST extraction is
   consumed only by worker classification; the registry already owns static
   metadata extraction for discovery. Inline PEP 723 blocks therefore remain
   inert comments parsed only by Python itself.

3. **Represent local packs uniformly as dictionaries.** Removing
   `WorkerPackProxy` eliminates special cases from namespace construction,
   metadata, diagnostics, CLI status, docs generation, and tests.

4. **Delete the worker-only main spec and move the retained extension contract
   into `serve-tools-packages`.** Forge's existing spec remains the canonical
   scaffold contract. Install and security documentation will describe
   dependencies as part of the installed OneTool environment.

5. **Do not migrate extension files.** Function-only files already load
   in-process. Files with PEP 723 comment blocks follow the same route, and
   imports fail normally if their dependencies are absent.

## Risks / Trade-offs

- **Extensions that depended on automatic `uv run` environments stop loading.**
  → This is the intended v3 contract removal; current Forge output never
  creates those files, and the required dependency model is documented.
- **Broad deletion can leave stale type checks or claims.**
  → Use completion searches across current source, tests, main specs, and
  non-historical docs, plus focused registry/docs-generation tests.
- **Import failures occur in the server process.**
  → Preserve the loader's existing per-module failure reporting and ensure one
  failed extension does not prevent unrelated packs from loading.
