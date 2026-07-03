# Design: Demos, proxy walkthrough, and framework-vs-product positioning

## Context

This is a docs/content-only change. No `src/` behavior changes. The implementer must not need
`wip/release-v3/*` — every fact needed is inlined below, copied verbatim from
`wip/release-v3/release-v3-report-2.md` (R4, lines 174-205 at the time of writing) and
`wip/release-v3/core-flow-deep-dive.md` (§E, "FastMCP 3.x Feature-Adoption Review").

Current state verified at `main`@`151a52b3` (2026-07-04):

- `docs/learn/` has no subdirectories (flat list of `.md` files: `quickstart.md`,
  `installation.md`, `configuration.md`, `direct-usage.md`, `security.md`,
  `explicit-calls.md`, `snippets.md`, `extension-tools.md`, `whats-new-v2.md`, `comparison.md`,
  `index.md`).
- No `docs/learn/demos/` or `examples/` directory exists anywhere in the repo.
- No proxy-namespace walkthrough exists anywhere in `docs/`.
- `mkdocs.yml` nav (`mkdocs.yml:141-153`) lists `Learn` pages explicitly; `not_in_nav:` /
  `exclude_docs:` (`mkdocs.yml:105-109`) currently only excludes `_wip/**`.
- `fastmcp>=3.1.1,<4` is already pinned at `pyproject.toml:23` — no new dependency needed for the
  narrator MCP server.
- `onetool direct run` (documented at `docs/learn/direct-usage.md`) requires
  `direct.host.enabled: true` and a bound `--port` in `onetool.yaml`; it accepts an inline command
  string, a `.py` file, or stdin (`-`); `--format raw|json|json_h|yml`; exit codes `0` success,
  `1` failure, `2` argument error.
- Proxy servers are configured under `servers:` in `onetool.yaml`
  (`docs/reference/cli/onetool-config.md:355-373` for stdio servers, `:377-393` for HTTP
  servers). Example already documented:

  ```yaml
  servers:
    local_tools:
      type: stdio
      command: npx
      args: ["-y", "some-mcp-server@latest"]
      timeout: 30
    docs_tools:
      type: stdio
      command: uvx
      args: ["docs-mcp-server"]
      tool_prefix: "docs_"     # Strip this prefix so docs_search.query() → search.query()
      inherit_env: true
  ```

- Proxy name-aliasing implementation: `src/ot/executor/naming.py:15-16` `canonicalize_name()`
  strips `-`/`_` and lowercases; `src/ot/executor/pack_proxy.py:96-104`
  (`_create_mcp_proxy_pack` docstring) states the contract:

  ```
  Allows calling proxied MCP tools using dot notation with automatic aliasing:
  - context7.resolve_library_id(library_name="next.js")
  - github.list_repositories()        # matches list-repositories
  - github.listRepositories()         # also matches list-repositories

  Supports fuzzy matching across naming conventions (snake_case, kebab-case, camelCase, PascalCase).
  ```

- Runtime proxy control: `src/ottools/ot_servers.py` — pack `ot_servers`, alias `srv`
  (`pack_aliases = ("srv",)`, line 16) — four tools: `enable(name=...)`, `disable(name=...)`,
  `restart(name=...)`, `status(name=...)`. Discovery (read-only) is separate:
  `ot.servers(pattern="", info="default")` lists configured servers with connection status,
  `enabled` flag, `call_as` name, and `tool_count` (`src/ot/meta/_discovery.py:430-457`).
- `chrome_util`/`play_util` are thin wrappers over the proxy manager with a `server=` override,
  implemented in the shared module `src/otdev/_inject_base.py` (report cites
  `src/otdev/tools/_inject_base.py:102-133`; the actual current path drops `tools/` — see
  proposal.md Impact for the flagged drift). Concretely:
  - `chrome_util` defaults `server="chrome_devtools"` (`src/otdev/tools/chrome_util.py:41`)
  - `play_util` defaults `server="playwright"` (`src/otdev/tools/play_util.py:45`)
  - Every tool function accepts `server: str = _SERVER` as a keyword override
    (e.g. `chrome_util.highlight_element(selector=..., server="chrome_devtools")`), and internally
    calls `proxy.call_tool_sync(server, tool, {...})` (`src/otdev/_inject_base.py:102-133`,
    functions `_eval_js`/`_exec_js`) — i.e. these packs are not a separate implementation, they
    are the proxy manager plus a JS-injection convenience layer.

## Goals / Non-Goals

**Goals:**

- Give every requirement in `specs/_nf-docs/spec.md` a concrete, unambiguous file to point at.
- Make the framework-vs-product contrast copy-pasteable from this document (no redrafting).
- Make the proxy walkthrough's required content list exhaustive and code-verified.
- Fully specify the narrator MCP server (it is the one piece of new code in this otherwise
  docs-only change) so the implementer does not have to invent a design.
- Preserve all seven demo scenarios verbatim from the report, with an explicit launch-priority
  split.

**Non-Goals:**

- Claims reconciliation (`claims.md` vs `comparison.md` number agreement) — `p18-docs-debt-sweep`.
- Rewriting the ot-ref skill / "tools-mastery" content — `p21-run-contract-and-command-index`.
- Any `src/` runtime behavior change.
- Building a cross-platform narrator (macOS `say` only, by explicit report direction: "on macOS a
  trivial `say`-wrapping stdio MCP server gives zero-dependency narration").
- Video/audio recording production — the deliverable is the *scripts*, not a produced recording.

## Decisions

### D1 — Positioning copy: exact text to place in README.md and docs/learn/comparison.md

Adapt (do not invent) from `core-flow-deep-dive.md` §E. Required content, as prose near the top of
each doc (exact wording may be adapted to fit surrounding style, but every fact below must appear
in both locations or via an explicit cross-reference from `comparison.md` to `README.md`):

> **Framework feature vs. installed product.** FastMCP is a toolkit for *building* MCP servers;
> Code Mode, ProxyProvider, and the Monty sandbox are ingredients a *developer* must adopt and
> expose when authoring their own MCP server. None of them reach an end user (a Claude Code /
> Cursor / Codex user) unless someone builds and ships a server around them. OneTool *is* that
> shipped server: it turns those framework capabilities into something a user installs and uses
> immediately, wrapped with 200+ curated tools, the param/alias/snippet forgiveness layer, ctx
> handles, the prompt + skill that teach an LLM to drive it, rich config, and a security model.
> **A framework capability you'd have to build vs. a product you install.**
>
> Corollary: adopting a FastMCP internal (Code Mode, ProxyProvider, Monty) is an *implementation*
> choice OneTool makes internally — never a *positioning* risk, because the story is the product,
> not the plumbing.

README placement: a new subsection near "The Solution" / before "Features" (see current
`README.md` structure — "The Problem" → "The Solution" → "Install" → ... → "Features"). Insert a
"Why not just use FastMCP Code Mode?" subsection after "The Solution" and before "Install".

`docs/learn/comparison.md` placement: add a short framing paragraph before or after the existing
"Scenario: Impact of tool usage" benchmark tables, using the same contrast, or a 2-3 sentence
version with a link back to the README subsection — either satisfies the spec's "or a
cross-reference to it" scenario.

### D2 — Proxy walkthrough: new file `docs/learn/mcp-proxy.md`

One new page (not folded into `configuration.md` or `explicit-calls.md`, since those pages serve
different lookup intents — config schema vs. invocation syntax; this page's job is the *narrative*
"any server becomes a namespace" story). Required sections, each satisfying one spec scenario:

1. **"Any MCP server is a Python namespace"** — the `servers:` config example (copy from
   `docs/reference/cli/onetool-config.md:355-373`, reproduced in Context above) plus the resulting
   call: `local_tools.some_tool(arg="value")`.
2. **"Calling conventions don't matter"** — the name-aliasing example from
   `pack_proxy.py:96-104` (reproduced in Context above), stated as prose: the same upstream tool
   `list-repositories` is callable as `github.list_repositories()` or `github.listRepositories()`.
   Reference `canonicalize_name()` (`src/ot/executor/naming.py:15-16`) as the mechanism.
3. **"Runtime control without a restart"** — `ot_servers` (`srv`) worked examples:
   ```python
   ot_servers.status(name="local_tools")
   ot_servers.disable(name="local_tools")
   ot_servers.enable(name="local_tools")
   ot_servers.restart(name="local_tools")
   ```
   plus the read-only discovery counterpart `ot.servers(info="default")`.
4. **"chrome_util / play_util are proxy companions, not replacements"** — state explicitly that
   both packs are thin wrappers over the same proxy manager with a `server=` override
   (cite `src/otdev/_inject_base.py:102-133`, `chrome_util.py:41`, `play_util.py:45`), and that a
   user can call the underlying `chrome_devtools`/`playwright` server's own tools directly
   (`chrome_devtools.something(...)` / `playwright.browser_navigate(...)`) alongside the
   annotation helpers in the same session — they are not alternatives to each other.

Link `docs/learn/mcp-proxy.md` from `docs/learn/index.md` and add it to `mkdocs.yml` nav under
`Learn`, after `Direct Usage` (natural reading order: config → invocation → direct CLI → proxy).

### D3 — Demos directory layout

```
docs/learn/demos/
  index.md                     # overview, launch-priority split, prerequisites
  narrator/
    say_server.py              # trivial macOS `say`-wrapping stdio MCP server
    README.md                  # setup: register under servers:, macOS-only note, test call
  01-forgiveness.sh
  02-codebase-to-whiteboard.sh
  03-secrets-commit.sh
  04-fewer-schemas.sh
  05-self-healing-browser.sh
  06-context-handle.sh
  07-five-packs-one-block.sh
```

Each `NN-slug.sh` is a standalone, commented shell script that:

- Assumes `onetool serve` is already running with `direct.host.enabled: true` bound to a known
  port (script takes `PORT` as `$1`, default `8765`).
- Narrates each step by calling `narrator.speak(text="...")` through
  `onetool direct run --port "$PORT"` before or after the substantive call, so playback narrates
  itself — no separate audio track needed.
- Drives the substantive steps via `onetool direct run --port "$PORT" "<pack.tool(...)>"`.
- Exits non-zero (via `set -e`) if any `onetool direct run` call fails, so the script is directly
  usable as a manual release test (spec scenario "Demos double as manual release tests").

Add `docs/learn/demos/**` to `mkdocs.yml`'s `not_in_nav:` block (alongside the existing
`_wip/**` entry) so individual demo scripts/READMEs don't need per-file nav entries; add a single
`Demos: learn/demos/index.md` entry to the `Learn` nav so the overview page is discoverable.

### D4 — Narrator MCP server: exact implementation

`docs/learn/demos/narrator/say_server.py`:

```python
#!/usr/bin/env python3
"""Zero-dependency macOS narrator MCP server for OneTool demos.

Wraps the macOS `say` command as a single MCP tool, proxied through OneTool.
Demonstrates the proxy story documented in docs/learn/mcp-proxy.md: any stdio
MCP server, including this one, becomes a callable Python namespace with no
OneTool-side code changes — register it under `servers:` and call
`narrator.speak(text=...)`.

macOS only. `say` ships with the OS; no extra dependency beyond the `fastmcp`
client library, already a OneTool dependency (pyproject.toml `fastmcp>=3.1.1,<4`).
"""

from __future__ import annotations

import subprocess
import sys

from fastmcp import FastMCP

mcp = FastMCP("narrator")


@mcp.tool()
def speak(text: str, voice: str = "Samantha") -> str:
    """Speak `text` aloud using the macOS `say` command.

    Args:
        text: The line to narrate.
        voice: macOS voice name (see `say -v ?` for the installed list).

    Returns:
        Confirmation string once `say` exits.
    """
    if sys.platform != "darwin":
        return "narrator.speak is macOS-only (say not available on this platform)"
    subprocess.run(["say", "-v", voice, text], check=True)
    return f"spoke: {text!r}"


if __name__ == "__main__":
    mcp.run()
```

`docs/learn/demos/narrator/README.md` must document the registration snippet:

```yaml
# In onetool.yaml
servers:
  narrator:
    type: stdio
    command: python
    args: ["docs/learn/demos/narrator/say_server.py"]
```

and a one-line smoke test: `onetool direct run --port 8765 "narrator.speak(text='OneTool online')"`.

### D5 — The seven demo scenarios (verbatim from the report)

Copied exactly from `wip/release-v3/release-v3-report-2.md` R4 (lines 174-205 at time of writing).
Each `NN-slug.sh` implements the corresponding bullet below; the implementer must not paraphrase
away any named tool call.

**Launch-priority split** (per the report's "launch-pick first three" guidance — demos 1-3 ship
for V3 launch; 4-7 ship in the same directory as backlog scenarios and are optional for the V3
release gate, but must still exist as runnable scripts once built):

1. **(required) Forgiveness demo**: sloppy calls that all work — `mem.search(q=)` (param prefix),
   `wb.draw()`/`excalidraw.draw()` (pack aliases), `github.listRepositories()`/
   `list_repositories()` (proxy name aliasing), typo → did-you-mean (post-R2, i.e. requires
   `p13-recovery-seams`).
2. **(required) Codebase → live whiteboard**: ripgrep/file exploration drawing the architecture
   on the Excalidraw canvas in real time, narrated per subsystem.
3. **(required) "We just committed our secrets file"**: guided init →
   `ot_secrets.encrypt()` → commit `age1enc:` secrets.yaml on camera → server boots, keychain
   decrypts (sells R3 — requires `p14-guided-encrypted-secrets`).
4. **(optional) One tool, 300 fewer schemas**: connect, `ot.packs()`, first call, `ot.stats()`
   token count.
5. **(optional) Self-healing browser**: proxied `playwright.*` + `play_util` annotation; kill the
   server mid-demo; agent recovers via `ot_servers.status()`/`restart()`.
6. **(optional) The 40KB result that never touched context**: big fetch → ctx handle →
   `ctx.toc`/`ctx.ask` → `mem.write`.
7. **(optional) Five packs, one run block**: PDF → convert → excel pivot → `db.query` →
   whiteboard chart as one Python glue block.

"Each demo doubles as a manual release test; on macOS a trivial `say`-wrapping stdio MCP server
gives zero-dependency narration." (verbatim, report R4)

### D6 — Worked template: demo 1 (forgiveness), fully specified

Given as a concrete template so the remaining six follow the same shape without ambiguity.
`docs/learn/demos/01-forgiveness.sh`:

```bash
#!/usr/bin/env bash
# Demo 1 (required, launch): Forgiveness — sloppy calls that all work.
# Usage: ./01-forgiveness.sh [PORT]
set -euo pipefail
PORT="${1:-8765}"
run() { onetool direct run --port "$PORT" "$1" --format raw; }
say() { run "narrator.speak(text=$1)"; }

say "'OneTool forgives sloppy calls. Watch.'"

say "'First: a shortened parameter name. mem dot search, q equals gold price.'"
run "mem.search(q='gold price')"

say "'Second: a pack alias. wb dot draw, instead of the full whiteboard pack name.'"
run "wb.draw(dsl='A[Start] -> B[Forgiven]')"

say "'Third: a proxied tool called camelCase instead of snake_case.'"
run "github.listRepositories()"

say "'Fourth: a typo in a tool name, self-corrected with a did-you-mean suggestion.'"
run "ot.tool_info(name='mem.serach')"

say "'Four sloppy calls. Zero failures.'"
```

`docs/learn/demos/index.md` must state, for every demo including this template, which capability
it exercises and which upstream change (if any) it depends on — mirroring D5's per-bullet
dependency notes.

## Implementation guardrails

These apply to whoever implements `tasks.md`:

- **No compatibility shims/aliases.** This change adds new docs and one new small server script;
  there is nothing to alias or deprecate. If a demo script's dependency (e.g. `p13`'s
  `did_you_mean`) has not landed yet, do not stub around it with a fake success path — stop and
  report the missing dependency instead of writing a script that fakes the beat.
- **No stubbing or TODO-deferral.** Every one of the seven demo scripts must contain real
  `onetool direct run` invocations against real tool calls named in D5/D6 — not placeholder
  echoes, not comments saying "TODO: implement". If a named tool/pack does not yet exist or does
  not behave as described, stop and report; do not write a script that would pass CI by doing
  nothing.
- **Every task that touches a runnable artifact (the narrator server, the demo scripts) must be
  verified by actually running it**, not just by reading the code back. `just check` alone does
  not exercise `docs/learn/demos/*.sh` (they are not part of the pytest suite) — the Verification
  group in tasks.md requires literally executing each script against a running OneTool instance.
- **Tests**: this change has no `src/` code, so there is no new unit/integration test suite to
  add. `just check` (lint+type+test) must still pass unchanged — it must not regress from adding
  `docs/learn/demos/narrator/say_server.py` (a plain script, not part of any package import graph,
  so it is not picked up by `mypy`/`pytest` collection; confirm this with the Verification
  commands below rather than assuming it).
- **Any listed acceptance `rg`/`test`/`grep` command in tasks.md's Verification group that must
  return empty or must find a match MUST actually be run, and its real output recorded** — not
  asserted from reading the file. This includes the "positioning phrase present" checks and the
  "demo script count" check.
- **Respect scope boundaries.** Do not touch `claims.md`/`comparison.md` number reconciliation
  (owned by `p18`) beyond adding the positioning cross-reference from D1. Do not touch
  `skills/ot-ref/` content (owned by `p21`).

## Risks / Trade-offs

- **[Risk] Demo scripts depend on Wave 1/2 changes landing first (p11, p13, p14, p16, p17).** If
  this change is implemented before those land, scripts 1 and 3 will fail their `onetool direct
  run` calls (no `did_you_mean`, no `ot_secrets.encrypt`, no `excalidraw` alias). → **Mitigation**:
  this proposal's Impact section states the dependency explicitly; tasks.md orders demo-script
  tasks after a dependency-check task, and the Verification section requires actually running each
  script, which will fail loudly (non-zero exit) rather than silently if a dependency is missing.
- **[Risk] macOS-only narrator excludes Linux/Windows demo playback.** → **Mitigation**: explicitly
  scoped as macOS-only per the report's own direction; `speak()` no-ops with a clear message on
  other platforms rather than crashing, so the substantive (`onetool direct run` tool calls)
  portion of each script still runs cross-platform even without audio.
- **[Risk] mkdocs `omitted_files: warn` may flag new `.md` files not in nav.** → **Mitigation**:
  add `docs/learn/demos/**` to `not_in_nav:` (D3) so per-demo READMEs don't trigger warnings;
  only `docs/learn/mcp-proxy.md` and `docs/learn/demos/index.md` need explicit nav entries.
- **[Trade-off] Demos 4-7 are marked optional for the V3 gate.** The report lists all seven as
  "candidate scenarios" but explicitly says "launch-pick first three" — treating 4-7 as launch-
  optional (while still requiring them to exist, scripted, per the exhaustive-scope-transfer rule)
  resolves that tension without inventing scope the report didn't state. If the maintainer wants
  all seven required for the V3 gate, that is a one-line change to tasks.md's Verification group.
