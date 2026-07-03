## 1. Preconditions

- [ ] 1.1 Confirm the Wave 1/2 dependencies this change relies on have landed: `p11-skills-standard-layout`, `p13-recovery-seams`, `p14-guided-encrypted-secrets`, `p16-extras-restructure`, `p17-pack-api-consistency`. Specifically verify: `src/otdev/tools/excalidraw.py` declares `pack_aliases = ("wb", "excalidraw")` (p17); `ot.tool_info` returns `did_you_mean` on a near-miss name (p13); `ot_secrets.encrypt`/`ot_secrets.init` exist (p14); the `whiteboard` extra is folded into `all` (p16). If any is missing, STOP and report — do not write a demo script around a dependency that has not landed (per design.md Implementation guardrails).

## 2. Positioning content (README + comparison)

- [ ] 2.1 Add a "Why not just use FastMCP Code Mode?" subsection to `README.md`, placed after "The Solution" and before "Install" (current structure: `README.md` — see repo for current section order). Content: the full contrast paragraph from `design.md` D1, verbatim or lightly adapted for README tone — must retain: FastMCP-is-a-toolkit framing, Code Mode/ProxyProvider/Monty named as developer-adopted ingredients, "OneTool *is* that shipped server" framing, the 200+ curated tools / forgiveness layer / ctx handles / prompt+skill / config+security list, and the closing line "a framework capability you'd have to build vs. a product you install."
- [ ] 2.2 Add the same contrast (or a 2-3 sentence version plus a link back to the README subsection) to `docs/learn/comparison.md`, placed near the existing "Scenario: Impact of tool usage" benchmark tables.
- [ ] 2.3 Add the "adopting a FastMCP internal is never a positioning risk" corollary sentence from `design.md` D1 to whichever of the two docs carries the fuller version (README, per 2.1).

## 3. MCP proxy walkthrough

- [ ] 3.1 Create `docs/learn/mcp-proxy.md` with the four required sections from `design.md` D2:
  - [ ] 3.1.1 "Any MCP server is a Python namespace" — reproduce the `servers:` stdio config example from `docs/reference/cli/onetool-config.md:355-373` and show the resulting `local_tools.some_tool(arg="value")` call.
  - [ ] 3.1.2 "Calling conventions don't matter" — reproduce the name-aliasing contract from `src/ot/executor/pack_proxy.py:96-104` (the `github.list_repositories()`/`github.listRepositories()` example) and cite `canonicalize_name()` at `src/ot/executor/naming.py:15-16` as the mechanism.
  - [ ] 3.1.3 "Runtime control without a restart" — worked examples for `ot_servers.status(name=...)`, `ot_servers.disable(name=...)`, `ot_servers.enable(name=...)`, `ot_servers.restart(name=...)` (pack `ot_servers`, alias `srv`, `src/ottools/ot_servers.py`), plus `ot.servers(info="default")` for read-only discovery.
  - [ ] 3.1.4 "chrome_util / play_util are proxy companions, not replacements" — state that both packs are thin wrappers over the proxy manager with a `server=` override, implemented in `src/otdev/_inject_base.py:102-133` (functions `_eval_js`/`_exec_js`), with `chrome_util` defaulting `server="chrome_devtools"` (`src/otdev/tools/chrome_util.py:41`) and `play_util` defaulting `server="playwright"` (`src/otdev/tools/play_util.py:45`); state explicitly that a user can call the underlying proxied server's own tools directly alongside the annotation helpers in the same session.
- [ ] 3.2 Link `docs/learn/mcp-proxy.md` from `docs/learn/index.md`.
- [ ] 3.3 Add `MCP Proxy: learn/mcp-proxy.md` to the `Learn` nav in `mkdocs.yml`, positioned after the `Direct Usage: learn/direct-usage.md` entry (`mkdocs.yml:148`).

## 4. Narrator MCP server

- [ ] 4.1 Create `docs/learn/demos/narrator/say_server.py` with the exact implementation in `design.md` D4 (FastMCP-based stdio server, single `speak(text, voice="Samantha")` tool wrapping macOS `say`, no-op message on non-`darwin` platforms).
- [ ] 4.2 Create `docs/learn/demos/narrator/README.md` documenting: the `servers:` registration snippet from `design.md` D4 (server name `narrator`, `type: stdio`, `command: python`, `args: ["docs/learn/demos/narrator/say_server.py"]`), the macOS-only caveat, and the smoke-test command `onetool direct run --port 8765 "narrator.speak(text='OneTool online')"`.
- [ ] 4.3 Run the smoke test on a macOS machine (or note in the PR/commit if run on non-macOS that the platform guard was exercised instead) and confirm exit code `0`.

## 5. Demo scripts — required for V3 launch

- [ ] 5.1 Create `docs/learn/demos/01-forgiveness.sh` implementing report scenario 1 (Forgiveness demo) exactly as specified in `design.md` D5/D6: `mem.search(q=...)` param-prefix call, `wb.draw()`/`excalidraw.draw()` pack-alias call, `github.listRepositories()`/`list_repositories()` proxy name-aliasing call, and a typo → `did_you_mean` call via `ot.tool_info(name=...)`. Use the worked template in `design.md` D6 as the base.
- [ ] 5.2 Create `docs/learn/demos/02-codebase-to-whiteboard.sh` implementing report scenario 2: ripgrep/file exploration (`ripgrep.search`/`ripgrep.count`, `file.read`/`file.grep`) drawing the architecture onto the Excalidraw canvas in real time via `whiteboard.open`/`whiteboard.draw`, narrated per subsystem via `narrator.speak(...)` calls between drawing steps.
- [ ] 5.3 Create `docs/learn/demos/03-secrets-commit.sh` implementing report scenario 3: guided `onetool init` secrets step → `ot_secrets.encrypt()` → commit an `age1enc:`-prefixed `secrets.yaml` on camera (narrated) → restart/boot the server and show the keychain-backed decrypt succeeding. Depends on `p14-guided-encrypted-secrets` (checked in task 1.1).

## 6. Demo scripts — optional backlog (must exist, non-blocking for V3 gate)

- [ ] 6.1 (optional) Create `docs/learn/demos/04-fewer-schemas.sh` implementing report scenario 4: connect, `ot.packs()`, first tool call, `ot.stats()` showing the token count.
- [ ] 6.2 (optional) Create `docs/learn/demos/05-self-healing-browser.sh` implementing report scenario 5: proxied `playwright.*` calls plus a `play_util` annotation call, then simulate killing the proxied server mid-demo and show the agent recovering via `ot_servers.status()`/`ot_servers.restart()`.
- [ ] 6.3 (optional) Create `docs/learn/demos/06-context-handle.sh` implementing report scenario 6: a large `webfetch.fetch(...)` call that returns a ctx handle instead of inline content, then `ctx.toc(...)`/`ctx.ask(...)` navigation, then `mem.write(...)` to persist the distilled result.
- [ ] 6.4 (optional) Create `docs/learn/demos/07-five-packs-one-block.sh` implementing report scenario 7: a single Python glue block (passed to `onetool direct run` as a `.py` file or heredoc) chaining `convert.pdf_to_md` → an Excel pivot via `excel.query`/`excel.write` → `db.query` → a `whiteboard.draw` chart, demonstrating five packs in one `run` block.

## 7. Demos index and nav

- [ ] 7.1 Create `docs/learn/demos/index.md`: overview of the demo set, the launch-priority split (demos 1-3 required, 4-7 optional backlog, per `design.md` D5), prerequisites (fresh `[all]`-extras install, `onetool init`, `direct.host.enabled: true`, the narrator server registered per section 4), and for every demo — including 01-forgiveness — which capability it exercises and which upstream change (if any) it depends on.
- [ ] 7.2 Add `docs/learn/demos/**` to the `not_in_nav:` block in `mkdocs.yml` (alongside the existing `_wip/**` entry, `mkdocs.yml:105-106`).
- [ ] 7.3 Add a single `Demos: learn/demos/index.md` entry to the `Learn` nav in `mkdocs.yml`, after the `MCP Proxy` entry added in task 3.3.

## Verification

- [ ] V.1 Positioning phrase present in both docs:
  ```bash
  rg -n "framework capability you'd have to build vs\. a product you install" README.md docs/learn/comparison.md
  ```
  Both files (or an explicit cross-reference from `comparison.md` to the README section) must match.
- [ ] V.2 Proxy walkthrough exists and covers the required concepts:
  ```bash
  test -f docs/learn/mcp-proxy.md
  rg -n "canonicalize_name|ot_servers|server=|chrome_util|play_util" docs/learn/mcp-proxy.md
  ```
  Must find matches for each concept, not just the file's existence.
- [ ] V.3 Demo directory structure complete:
  ```bash
  ls docs/learn/demos/*.sh | wc -l   # expect 7
  test -f docs/learn/demos/index.md
  test -f docs/learn/demos/narrator/say_server.py
  test -f docs/learn/demos/narrator/README.md
  ```
- [ ] V.4 Every demo script actually invokes `onetool direct run` and narrates via the proxy:
  ```bash
  for f in docs/learn/demos/*.sh; do rg -l "onetool direct run" "$f" || echo "MISSING run: $f"; done
  for f in docs/learn/demos/*.sh; do rg -l "narrator.speak" "$f" || echo "MISSING narration: $f"; done
  ```
  Both loops must produce no `MISSING` lines.
- [ ] V.5 mkdocs nav updated:
  ```bash
  rg -n "learn/mcp-proxy.md|learn/demos/index.md|demos/\*\*" mkdocs.yml
  ```
  Must find the two new nav entries and the `not_in_nav` glob.
- [ ] V.6 Demos actually run start-to-finish on a fresh `[all]` install (manual, not scriptable in CI — run once per required demo and record the result):
  ```bash
  # In a fresh environment:
  uv tool install 'onetool-mcp[all]'
  onetool init --config ~/.onetool-demo
  # enable direct.host in ~/.onetool-demo/onetool.yaml, register the narrator server per
  # docs/learn/demos/narrator/README.md, then start the server:
  onetool serve --config ~/.onetool-demo/onetool.yaml &
  ./docs/learn/demos/01-forgiveness.sh 8765
  ./docs/learn/demos/02-codebase-to-whiteboard.sh 8765
  ./docs/learn/demos/03-secrets-commit.sh 8765
  ```
  Every script must exit `0`. This is the direct verification of the "Demo runs start-to-finish
  on a fresh install" and "Demos double as manual release tests" spec scenarios — do not mark
  this task done from reading the scripts alone.
- [ ] V.7 Repo-wide gate:
  ```bash
  just check
  ```
  Must pass unchanged (no `src/` files touched by this change).
