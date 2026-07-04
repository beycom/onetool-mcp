# OneTool demos

Scripted, replayable demonstrations of OneTool's most differentiating — and most undersold —
capabilities. Each demo is a standalone shell script driven entirely by `onetool direct run`
(itself a demonstration of the Direct CLI) and narrated aloud through a proxied macOS `say`
server. Every script exits non-zero if any tool call fails, so **each demo doubles as a manual
release test**.

## Prerequisites

1. A fresh install with all tools:

   ```bash
   uv tool install 'onetool-mcp[all]'
   onetool init --config ~/.onetool-demo
   ```

2. Enable the Direct API in `~/.onetool-demo/onetool.yaml`:

   ```yaml
   direct:
     host:
       enabled: true
   ```

3. Register the narrator server (see [narrator/README.md](narrator/README.md)) under `servers:`.

4. Start the server and note the printed Direct API port:

   ```bash
   onetool serve --config ~/.onetool-demo/onetool.yaml
   ```

5. Run a demo with the port as its one argument:

   ```bash
   ./docs/learn/demos/01-forgiveness.sh 8765
   ```

Narration is macOS-only; on other platforms the substantive tool calls still run (the narrator
no-ops with a message).

## Launch priority

Demos **1–3 are required for the V3 launch**. Demos **4–7 are optional backlog** scenarios — they
exist as runnable scripts in this directory but are not part of the V3 release gate.

## The demos

| # | Script | Capability shown | Depends on |
|---|--------|------------------|------------|
| 1 (required) | `01-forgiveness.sh` | The forgiveness layer: param-prefix (`mem.search(q=)`), pack alias (`wb.draw`), proxy name-aliasing (`github.listRepositories()`), typo → did-you-mean (`ot.tool_info`) | p17 (`excalidraw` alias), p13 (`did_you_mean`) |
| 2 (required) | `02-codebase-to-whiteboard.sh` | Explore a codebase (ripgrep/file) and draw its architecture live on the Excalidraw canvas, narrated per subsystem | p16 (`whiteboard` in `[all]`) |
| 3 (required) | `03-secrets-commit.sh` | Encrypted secrets: `ot_secrets.set`/`encrypt`, commit `age1enc:` ciphertext, keychain-backed transparent decrypt | p14 (guided encrypted secrets) |
| 4 (optional) | `04-fewer-schemas.sh` | One tool, hundreds fewer schemas: `ot.packs()`, first call, `ot.stats()` token count | — |
| 5 (optional) | `05-self-healing-browser.sh` | Proxied `playwright.*` + `play_util` annotation; kill the server mid-demo; recover via `ot_servers.status()`/`restart()` | a configured `playwright` proxy server |
| 6 (optional) | `06-context-handle.sh` | A large `webfetch.fetch(...)` returns a ctx handle; `ctx.toc`/`ctx.ask` navigation; `mem.write` to persist | `[util]` extra (ctx) |
| 7 (optional) | `07-five-packs-one-block.sh` | Five packs in one Python glue block: `convert` → `excel` pivot → `db.query` → `whiteboard` chart | `[util]` + `[dev]` extras |

Demos 6 and 7 use a placeholder handle / sample inputs — substitute the real handle printed by the
fetch (demo 6) and a real PDF/db_url (demo 7) when running them live.
