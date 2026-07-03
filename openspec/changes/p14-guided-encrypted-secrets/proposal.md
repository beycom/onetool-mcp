## Why

OneTool's encrypted-secrets feature is technically sound (age X25519 via `pyrage`, private
identity in the OS keychain, `age1enc:` values safe to commit, transparent lazy decrypt) but is
undersold and has real safety gaps that block marketing it as "safe to commit":

- There is no CLI entry point. Setting it up today requires an already-wired MCP client issuing
  raw `__onetool ot_secrets.init()` calls, and step one is hand-writing **plaintext** YAML
  (`docs/learn/security.md:158-162,177-178`).
- There is no `set`/`get`. Adding one secret means editing plaintext then re-encrypting the whole
  file; there is no single-value encrypt-in-place and no round-trip verification
  (`src/ottools/ot_secrets.py:23` `__all__` has no `set`/`get`).
- `file=` is required on `encrypt()`, `rotate()`, and `audit()` instead of defaulting to the
  configured secrets path (`src/ottools/ot_secrets.py:106,253,346`).
- A verified adversarial audit found four hardening gaps that undermine the "safe to commit"
  claim: `encrypt()`/`rotate()` default to writing a **plaintext** `.bak` copy
  (`src/ottools/ot_secrets.py:148-151,296-299`); every keychain call is a bare `keyring.set/get_password`
  with no backend inspection, so a headless host can silently pick a plaintext `keyrings.alt`
  backend and write the **private age identity in cleartext**
  (`src/ottools/ot_secrets.py:82,94-96,122`; `src/ot/config/secrets.py:127`); `rotate()` is
  non-atomic — the new identity is only in RAM until after the file write, so a crash between
  writing new-key ciphertext and updating the keychain makes all secrets unrecoverable
  (`src/ottools/ot_secrets.py:303-332`); and only the init-template copy sets `0600` on
  `secrets.yaml` — `encrypt()`/`rotate()` write via `open("w")` (umask-dependent) and `copy2`
  propagates that mode to the plaintext backup (`src/ot/paths.py:283-284` vs `ot_secrets.py`
  write paths).
- The most common first-run failure across five key-gated packs says only
  `"Error: {SECRET} secret not configured"` — it names the secret but never says where or how to
  set it (`packages/onetool-pack/src/otpack/http.py:62,148,163`).

This change converges the two divergent `onetool init` code paths into one guided flow, adds
`set`/`get` with a hard no-plaintext-leak invariant, closes the four hardening gaps, and extends
the missing-key error string — turning a real differentiator into something users can actually
discover and trust.

## What Changes

- **BREAKING**: `ot_secrets.encrypt()` and `ot_secrets.rotate()` default `backup=False`
  (previously `backup=True`, which wrote a persistent plaintext `.bak` file by default). Callers
  that relied on the implicit backup must now pass `backup=True` explicitly.
- Converge the `onetool init` TUI (`src/onetool/cli.py:382-480`) with the `ensure_ot_dir` init
  path (`src/ot/paths.py:246`) so both create `secrets.yaml` from the template, and add a
  guided "Set up encrypted secrets?" step: prompts for key/value pairs, writes them, then calls
  `ot_secrets.init()` and `ot_secrets.encrypt()` in one shot so no plaintext value is ever left on
  disk.
- Add `ot_secrets.set(key=, value=, file=None)`: encrypts a single value in place against the
  stored identity, with round-trip verification before the write is committed.
- Add `ot_secrets.get(key=, file=None, out_file=None)`: **never** returns the plaintext value in
  the tool result (existence/metadata only, or writes the decrypted value to a caller-specified
  `0600` file when `out_file` is given).
- Default `file=` to the configured secrets path (loaded `--secrets` path, else
  `<config dir>/secrets.yaml`) on every `ot_secrets` op that currently requires it
  (`encrypt`, `status`, `rotate`, `audit`, plus the new `set`/`get`).
- Harden `encrypt()`/`rotate()`: default `backup=False`; atomic temp-file + `os.replace()` writes;
  explicit `os.chmod(0o600)` on the written file and on any backup; keyring backend validated
  (allow-listed secure backend) before any keychain write or the plaintext-fallback risk applies;
  `rotate()` persists the new identity to the keychain only after the new file has been written
  and every value verified to decrypt with the new identity (temp-file + rename, no truncation
  window).
- Add keyring backend validation: after `init()` (and before any later keychain read/write),
  assert `keyring.get_keyring()` resolves to an allow-listed secure backend (macOS `Keyring`,
  Windows `WinVaultKeyring`, Linux `SecretService`/`libsecret`/`kwallet`); error loudly — naming
  the insecure backend found — on `fail`/`null`/`chainer`/third-party (`keyrings.alt`) backends.
- Harden decrypt robustness: `base64.b64decode(..., validate=True)` in
  `src/ot/config/secrets.py:137` and `src/ottools/ot_secrets.py:318`.
- Align the two "no identity found" guidance strings in `src/ot/config/secrets.py:131` and
  `src/ottools/ot_secrets.py:126` to identical canonical text.
- Sanitize proxy connect-error strings before they are surfaced to the agent or logs
  (`src/ot/proxy/manager.py:489,733` currently store the raw `str(e)`, which could echo a bearer
  token built from a decrypted secret).
- Extend the shared missing-key error string (`packages/onetool-pack/src/otpack/http.py:62,148,163`
  — `api_headers()`, `require_api_key()`, `check_api_key()`) to name both the secret **and** where
  to set it (`secrets.yaml` / `ot_secrets.set()` / the guided `onetool init` flow).
- Docs: add `pyrage`/`keyring` to the "Requires" section of `docs/reference/tools/ot_secrets.md:33-35`.

## Capabilities

### New Capabilities

(none — all changes extend existing capabilities)

### Modified Capabilities

- `ottools/tool-secrets`: adds `set()`/`get()`, keyring backend validation, `file=` default
  resolution, atomic + `0600` writes, `backup=False` default, decrypt robustness, and the
  missing-secret error-guidance contract for the shared `otpack.http` helpers.
- `onetool-cli`: `onetool init` guided setup gains a "Set up encrypted secrets?" step and always
  materialises `secrets.yaml`, converging with the `ensure_ot_dir` first-run path.
- `serve-mcp-proxy`: proxy connect-error strings surfaced to the agent/logs are sanitized before
  being stored/returned.

## Impact

- Affected code:
  - `src/ottools/ot_secrets.py` — new `set()`/`get()`, backend validation, atomic writes, `0600`
    enforcement, `backup=False` default, `file=` default resolution, `base64` strict decode.
  - `src/ot/config/secrets.py` — `base64` strict decode, guidance-string alignment.
  - `src/onetool/cli.py` (`init_callback`, lines 382-480) — secrets step in the guided TUI.
  - `src/ot/_tui.py` — new masked-input prompt helper for secret values.
  - `src/ot/paths.py` — no functional change expected, but `ensure_ot_dir`'s `secrets.yaml`
    materialisation is the convergence target for the CLI `init` flow.
  - `packages/onetool-pack/src/otpack/http.py` — missing-key error string extended at all three
    call sites (`api_headers`, `require_api_key`, `check_api_key`).
  - `src/ot/proxy/manager.py` — connect-error string sanitization.
  - `docs/reference/tools/ot_secrets.md` — dependency documentation.
  - Tests: `tests/ottools/unit/tools/test_secrets.py`, `tests/unit/core/test_secrets.py`,
    `tests/unit/core/test_init_redesign.py`, `src/ot/proxy` test coverage.
- Dependencies on sibling changes (do not implement here):
  - `p15-install-flow-and-mcp-config` owns the bootstrap installer and `onetool init mcp-config`
    (report R3 items 0 and 3). This change's guided secrets step is designed to compose with
    whatever `onetool init` shape p15 lands, but does not depend on p15 landing first.
  - `p18-docs-debt-sweep` owns the broader R3 item 5 docs sweep (3.12/uv prerequisites, `kb.py`
    package name, canonical tool count, `ot.status` README row). **Ownership note for the
    maintainer**: the wave map assigns "secrets pack deps, guidance drift" to p18 verbatim, but
    this change's task brief explicitly assigned the same two bullets (pyrage/keyring deps doc,
    and the `config/secrets.py:131` vs `ot_secrets.py:126` guidance-string drift) to p14 because
    they are directly coupled to the hardening work done here. This change implements both; if
    p18 is drafted independently, its author should drop these two items to avoid duplicate work.
  - `p16-extras-restructure` owns the `[whiteboard]`→`[util]` extras move; unrelated to this
    change's scope.
- No new runtime dependencies: `pyrage` and `keyring` are already core `pyproject.toml`
  dependencies (`pyproject.toml:41-42`), not gated behind an extra.
