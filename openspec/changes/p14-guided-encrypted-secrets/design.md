## Context

**What exists today (verified against `main`@`151a52b3`, 2026-07-04):**

- `src/ottools/ot_secrets.py` — the `ot_secrets` pack (pack name `ot_secrets`, short alias `sec`,
  `pack_aliases = ("sec",)` at line 21). `__all__` at line 23 currently lists
  `["audit", "encrypt", "init", "rotate", "status"]` — no `set`/`get`.
  - `_SERVICE = "onetool"`, `_KEY_IDENTITY = "age_identity"`, `_KEY_PUBKEY = "age_pubkey"`,
    `_KEY_LABEL = "age_label"` (lines 32-35) — the three keychain entries.
  - `init()` (lines 68-103) generates a `pyrage.x25519.Identity`, stores private key, public key,
    and label via three `keyring.set_password(_SERVICE, ...)` calls (lines 94-96).
  - `encrypt(*, file: str, backup: bool = True)` (lines 106-182): requires `file`; `backup=True`
    is the current default; on `backup`, `shutil.copy2(path, backup_path)` copies the
    **pre-encryption plaintext** to `<file>.bak` (lines 148-151); writes via `path.open("w")` +
    `yaml.dump` (lines 171-172) — no atomicity, no `chmod`.
  - `status(*, file: str | None = None)` (lines 185-250): `file` is already optional here (the
    one op that isn't required).
  - `rotate(*, file: str, backup: bool = True)` (lines 253-343): requires `file`; same
    plaintext-`.bak`-by-default issue (lines 296-299); decrypts each value with the **old**
    identity, re-encrypts with a **newly generated** identity, writes the file (lines 327-328),
    then **only after the file write** updates the three keychain entries to the new identity
    (lines 330-332) — the crash window between file-write and keychain-update is the "old key
    gone from file, new key gone from keychain" data-loss scenario.
  - `audit(*, file: str)` (lines 346-399): requires `file`; read-only, already safe (returns key
    names only).
  - `_require_keyring()` (lines 39-47) and `_require_pyrage()` (lines 50-58) are the only import
    guards; neither inspects which keyring **backend** got selected.
- `src/ot/config/secrets.py` — `load_secrets()` (lines 46-145) does the transparent lazy decrypt:
  scans loaded secrets for the `age1enc:` prefix (line 109), and only if any are found, imports
  `keyring`/`pyrage`, reads the private key via `keyring.get_password("onetool", "age_identity")`
  (line 127; bare call, no backend check), and decrypts each value (lines 134-140) using
  `base64.b64decode(encoded)` (line 137, **no** `validate=True`). If no private key is found, it
  raises `SecretDecryptionError` with the message at lines 129-132: `"Encrypted secrets found in
  secrets file but no age identity is stored in the OS keychain. Run: __onetool
  ot_secrets.init()"`. Compare to `ot_secrets.py:126`: `"No identity found in keychain. Run
  ot_secrets.init() first."` — different phrasing, one with the `__onetool` trigger prefix.
- `src/ot/paths.py` — `INIT_TEMPLATE_FILES` (lines 32-40) includes `"secrets-template.yaml"`.
  `ensure_ot_dir()` (lines 246-311) copies every template file to the ot dir if it doesn't already
  exist, and specifically `chmod(stat.S_IRUSR | stat.S_IWUSR)` (i.e. `0600`) **only** when
  `dest_name == "secrets.yaml"` (lines 283-284). This path is reached from `onetool serve`'s
  first-run prompt (`src/onetool/cli.py:712-728`, "Initialize now?").
- `src/onetool/cli.py` — `init_callback()` (lines 382-480) is the **separate** `onetool init`
  command. It has its own `_exts` list (lines 440-446: `prompts.yaml`, `servers.yaml`,
  `security.yaml`, `diagram.yaml`, `snippets.yaml`) and its own copy helpers (`_copy_file` at
  line 330, `_copy_diagram` at line 350, `_write_onetool_yaml` at line 264) — it never calls
  `ensure_ot_dir()` and never touches `secrets.yaml`. This is the divergence the report calls out:
  two init code paths, only one of which creates `secrets.yaml`.
- `packages/onetool-pack/src/otpack/http.py` — three call sites emit the identical bare string
  `f"{secret_name} secret not configured"`: `api_headers()` line 62 (`raise ValueError(...)`),
  `require_api_key()` line 148 (`return "", f"Error: {secret_name} secret not configured"`),
  `check_api_key()` line 163 (`return f"Error: {secret_name} secret not configured"`). The task
  brief named lines 148/163; line 62 was found during verification and is the same defect class,
  so it is included.
- `src/ot/proxy/manager.py` — `self._errors[name] = str(e)` at lines 489 and 733 stores the raw
  exception string from a failed MCP server connection attempt; this can surface to the agent via
  `ot.servers()`/status output. httpx normally omits header values from its exception `str()`, so
  the likelihood of a leaked bearer token is low, but it is not verified never to happen.
- `docs/reference/tools/ot_secrets.md:33-35` — the "Requires" section currently lists only "OS
  keychain support"; it omits the `pyrage`/`keyring` Python package dependencies that
  `ot_secrets.py:25-30`'s `__ot_requires__` already declares.
- `src/ot/_tui.py` (79 lines total) — the existing sync TUI primitives: `ask_checkbox` (line 55),
  `ask_text_sync` (line 72). Both wrap `questionary` calls in `try/except KeyboardInterrupt:
  return None`. There is no masked/password prompt helper yet.
- Installed `keyring` (25.7.0) backend modules (verified locally): secure —
  `keyring.backends.macOS.Keyring`, `keyring.backends.Windows.WinVaultKeyring`,
  `keyring.backends.SecretService.Keyring`, `keyring.backends.libsecret.Keyring`,
  `keyring.backends.kwallet.DBusKeyring`, `keyring.backends.kwallet.DBusKeyringKWallet4`;
  insecure/no-op — `keyring.backends.fail.Keyring` (raises on use),
  `keyring.backends.null.Keyring`, `keyring.backends.chainer.ChainerBackend`. Third-party
  `keyrings.alt` backends (e.g. `keyrings.alt.file.PlaintextKeyring`) are not part of the
  `keyring` package and cannot be enumerated — this is why the validation MUST be an allow-list
  (reject anything not explicitly recognised as secure), not a deny-list.
- Existing atomic-write idiom already used elsewhere in the repo (`src/otutil/tools/file.py:1852-1870`):
  `tempfile.mkstemp(dir=parent, prefix=".tmp_", suffix=...)` → write via `os.fdopen(fd, "wb")` →
  `Path(temp_path).replace(resolved)`, with `Path(temp_path).unlink()` cleanup on exception. This
  is the pattern to follow for `ot_secrets.py`'s atomic writes rather than inventing a new one.
- `src/ot/config/loader.py:523-525` — `get_loaded_secrets_path()` returns the most recently loaded
  `--secrets` path (or `None` if the server wasn't started with one). `src/ot/paths.py:133-144` —
  `get_config_dir()` returns the ot dir (`config_path.parent`). Together these are the two inputs
  for resolving a default secrets file path when `file=` is omitted.

## Goals / Non-Goals

**Goals:**

- One `onetool init` flow creates `secrets.yaml` and offers a guided encrypted-secrets setup that
  never leaves a plaintext value on disk.
- `ot_secrets.set()`/`get()` exist, with `get()` structurally incapable of returning the plaintext
  value in the tool result (the "audit/status emit names only" invariant extended to `get()`).
- `file=` has a sane default on every `ot_secrets` op so callers don't have to know the path.
- The four verified hardening gaps (plaintext `.bak` default, no keyring backend validation,
  non-atomic `rotate()`/`encrypt()`, missing `0600` enforcement) are closed, so "safe to commit"
  is actually true.
- The missing-key error string tells the caller both *what* is missing and *how* to fix it.

**Non-Goals:**

- The bootstrap installer and `onetool init mcp-config` (report R3 items 0 and 3) — owned by
  `p15-install-flow-and-mcp-config`.
- The `[whiteboard]`→`[util]` extras move — owned by `p16-extras-restructure`.
- The broader docs sweep (3.12/uv prerequisites, `kb.py` package name, tool-count drift,
  `ot.status` README row) — owned by `p18-docs-debt-sweep`. Only the two secrets-specific doc/
  guidance items explicitly assigned to this change are in scope here (see proposal.md Impact).
- Clipboard support for `get()`. A caller-specified `out_file` (written `0600`, deleted by the
  caller when done) satisfies the "never in the tool result" requirement without adding a new
  clipboard dependency (`pyperclip` or similar is not currently a project dependency and nothing
  in the codebase does text-clipboard I/O — `ot_image`'s clipboard support is image-only, via
  `PIL.ImageGrab`, and not reusable here).
- Changing the `age`/`pyrage` cryptographic scheme itself — it is already correct per the
  report's adversarial audit; only the operational gaps around it are in scope.

## Decisions

### 1. Converge the two `onetool init` code paths by extending the CLI TUI, not by calling `ensure_ot_dir()`

`init_callback()` (`src/onetool/cli.py:382-480`) keeps its own `_exts`/`_copy_file` machinery
(rather than switching to `ensure_ot_dir()`) because the two paths solve different problems:
`ensure_ot_dir()` bulk-copies every template unconditionally (used for the zero-interaction
`onetool serve` first-run path), while `init_callback()` is a selective, checkbox-driven flow.
Converging them means adding `"secrets.yaml"` as a new entry in the `_exts` selection list (line
440-446) so the *same* selective-copy mechanism (`_copy_file`, line 330) materialises it, keeping
one code path per interaction style but guaranteeing both eventually produce a `secrets.yaml` on
disk when requested.

Alternative considered — make `init_callback()` call `ensure_ot_dir()` and drop `_exts` entirely:
rejected, because `ensure_ot_dir()`'s "copy everything, skip only if it already exists" semantics
don't match the guided/selective UX the report explicitly asks to preserve (checkbox multi-select
already exists and is called out as reusable infrastructure).

### 2. The guided secrets step calls `ot_secrets.init()`/`encrypt()` as plain in-process function calls

`src/onetool/cli.py` already imports directly from `ot.*` packages in-process (e.g.
`from ot.paths import ensure_ot_dir` at line 722). `ottools.ot_secrets` has no MCP-runtime
dependency — `LogSpan` (from `otpack`) works standalone, and `init()`/`encrypt()` are plain
functions. The CLI flow after collecting key/value pairs will:

1. Write the pairs as plaintext to the just-created `secrets.yaml` (via the existing
   `_safe_write`/YAML-dump pattern).
2. Call `ot_secrets.init()` in-process (skip if an identity already exists — surface the "already
   exists" message and let the user choose to reuse it or pass `force=True` interactively).
3. Call `ot_secrets.encrypt(file=<path>, backup=False)` in-process.
4. Call `ot_secrets.audit(file=<path>)` and assert `safe == True` before printing success — if not
   safe, this is a bug in the flow (not a user-facing edge case) and the command must fail loudly
   rather than claim success.

Alternative considered — spawn a `onetool direct run 'ot_secrets.init(); ...'` subprocess: rejected
as unnecessary process/serialization overhead for a single-shot CLI flow that is already running
Python in-process; it would also require duplicating error handling for a code path that already
returns structured dicts.

### 3. Masked value entry: add `ask_password_sync()` to `src/ot/_tui.py`

Follows the exact shape of the existing `ask_text_sync()` (line 72): wraps
`questionary.password(prompt, style=APP_STYLE).ask()` in the same
`try/except KeyboardInterrupt: return None` pattern. `questionary.password` is part of the
`questionary` API already installed as a dependency (used elsewhere for `ask_text`/`ask_select`/
`ask_checkbox`) — no new dependency.

### 4. `set()` design: encrypt-in-place with round-trip verification, not a thin wrapper around `encrypt()`

`ot_secrets.set(*, key: str, value: str, file: str | None = None)`:

1. Resolve `file` via the shared default-resolution helper (Decision 6).
2. Load existing YAML (or start from `{}` if the file doesn't exist yet — `set()` may be the
   first write to a fresh `secrets.yaml`).
3. Validate the keyring backend (Decision 5) if an identity exists.
4. If an identity exists in the keychain: encrypt `value` with the stored public key, then
   **immediately decrypt the produced ciphertext with the same identity** and assert it equals
   `value` before writing anything to disk — this is the "round-trip verification" the report
   calls out as missing. Store `age1enc:<ciphertext>`.
5. If no identity exists: store the plain value and return a `warning` field
   (`"No age identity found — value stored in plaintext. Run ot_secrets.init() then
   ot_secrets.encrypt() to secure it."`), matching today's `encrypt()`/`rotate()` "no identity"
   error pattern rather than silently succeeding with a false sense of security.
6. Write atomically (Decision 7) and `chmod(0o600)` (Decision 8).

Alternative considered — `set()` always writes plaintext then calls `encrypt()` internally:
rejected because it reintroduces exactly the "plaintext hits disk" window (even transiently) that
the report identifies as the core problem; encrypting in memory before the first write avoids it
entirely.

### 5. `get()` design: never return the plaintext value in the tool result

`ot_secrets.get(*, key: str, file: str | None = None, out_file: str | None = None)`:

- Always returns `{"found": bool, "encrypted": bool}` (plus `error`/`status` on failure) — never a
  `value` key.
- If `out_file` is provided: decrypt (if `age1enc:`-prefixed) or read as-is (if plain), write the
  value to `out_file`, `chmod(out_file, 0o600)`, and add `{"written_to": out_file}` to the result.
  The value itself never enters the returned dict, the LogSpan, or any log line.
- This is a hard invariant, not a default that callers can override: there is intentionally no
  `include_value=True` escape hatch, because any such flag would eventually get set by an agent
  that "just wants to see the secret," reintroducing the exfiltration risk the report flags
  (tool result → agent transcript → host logs).

### 6. `file=` default resolution: new `_resolve_secrets_file()` helper in `ot_secrets.py`

```
def _resolve_secrets_file(file: str | None) -> Path:
    if file is not None:
        return Path(file).expanduser()
    from ot.config.loader import get_loaded_secrets_path
    loaded = get_loaded_secrets_path()
    if loaded is not None:
        return Path(loaded).expanduser()
    from ot.paths import get_config_dir
    return get_config_dir() / "secrets.yaml"
```

Applied to `encrypt`, `status`, `rotate`, `audit`, `set`, `get` — all become `file: str | None =
None`. `init()` is unaffected (it never took a `file` parameter — it only touches the keychain).
`get_config_dir()` raises `RuntimeError` if no config is loaded; that propagates as-is (an
`ot_secrets` call with no config loaded and no explicit `file=` is a genuine caller error).

### 7. Atomic writes: reuse the `tempfile.mkstemp` + `Path.replace()` idiom already in the repo

`encrypt()`, `rotate()`, and `set()` write via
`tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=".yaml")` → write encrypted YAML to the
fd → `os.chmod(temp_path, 0o600)` → `Path(temp_path).replace(path)`, matching
`src/otutil/tools/file.py:1852-1870`. On any exception before the replace, the temp file is
unlinked and the original file is left untouched — this closes the non-atomic-write / truncation
risk the report calls out for both `encrypt()` and `rotate()`.

For `rotate()` specifically: decrypt-verify-then-persist ordering is:
1. Decrypt every `age1enc:` value with the **old** identity (already required to build the
   re-encrypted file).
2. Generate the new identity; re-encrypt every value; **decrypt each new ciphertext with the new
   identity and assert equality with the original plaintext** (round-trip verification, extending
   the same principle as `set()`).
3. Write the new file atomically (temp + replace) at `0600`.
4. Only after the atomic replace succeeds, update the three keychain entries to the new identity.

This ordering means a crash before step 3 completes leaves the **old** file and **old** keychain
identity intact (rollback-safe); a crash after step 3 but before step 4 leaves a new-key file with
the old identity still in the keychain — recoverable by re-running `rotate()` (idempotent: it
would fail to decrypt with the mismatched identity, which is a clear, diagnosable error, not
silent data loss). This is the "persist to keychain before writing the file, or keep the old
identity until the new file round-trips" fix from the report, using the round-trip-first variant
since it doesn't require a fourth keychain slot (`age_identity_prev`).

### 8. `0600` enforcement: explicit `os.chmod()` after every secrets-file write, including backups

`encrypt()`/`rotate()`/`set()` call `os.chmod(path, 0o600)` immediately after the atomic replace
(mkstemp already creates the temp file at `0600` on POSIX, but the explicit chmod after replace
makes the guarantee independent of platform/umask behavior and covers Windows). When `backup=True`
is explicitly passed, the `.bak` file is also `chmod(0o600)` after `shutil.copy2()`.

### 9. Backup default: flip to `backup=False`, keep the plaintext-backup option opt-in

Of the three fixes the report offers (default off / encrypted backup / `0600` temp deleted on
success), this design picks **default `backup=False`**:

- Simplest to implement and verify (a straight default-value flip plus a `0600` chmod on the
  opt-in path).
- An encrypted backup is rejected as unnecessary complexity — it would need its own key-management
  story (encrypt the backup with what? the same key defeats the point if the concern is disk
  persistence of the plaintext).
- A `0600` temp-file-deleted-on-success backup is rejected because it provides no recovery value:
  if the concern is "developer wants a way back to the pre-encryption state," deleting it on
  success removes exactly the case where you'd want it (a working encryption run) and keeps it
  only for the failure case (where the original file is untouched anyway, since the write is now
  atomic per Decision 7) — i.e. it protects against nothing once atomicity is in place.
- Explicit `backup=True` remains available for anyone who wants an unencrypted recovery copy and
  understands the tradeoff; it is now `0600` instead of umask-dependent.

### 10. Keyring backend validation: allow-list, checked before every keychain write and read

`_assert_secure_keyring_backend(kr) -> None` in `ot_secrets.py`:

```
_SECURE_BACKENDS = {
    "keyring.backends.macOS.Keyring",
    "keyring.backends.Windows.WinVaultKeyring",
    "keyring.backends.SecretService.Keyring",
    "keyring.backends.libsecret.Keyring",
    "keyring.backends.kwallet.DBusKeyring",
    "keyring.backends.kwallet.DBusKeyringKWallet4",
}

def _assert_secure_keyring_backend(kr: Any) -> None:
    backend = kr.get_keyring()
    qualname = f"{type(backend).__module__}.{type(backend).__qualname__}"
    if qualname not in _SECURE_BACKENDS:
        raise RuntimeError(
            f"Insecure or unavailable OS keyring backend detected: {qualname}. "
            "OneTool refuses to store the age private key in this backend "
            "(it may be a plaintext fallback). Configure a secure OS keychain "
            "(macOS Keychain, Windows Credential Locker, or a Secret "
            "Service/KWallet/libsecret provider on Linux) and retry."
        )
```

Called at the top of `init()` (before any `set_password`), and at the top of every op that reads
the identity from the keychain (`encrypt`, `rotate`, and the transparent-decrypt path in
`config/secrets.py`) — not just "after init()" — because the backend can differ between the
process that ran `init()` and a later process reading the keychain (different environment,
different container). This is an **allow-list**, not a deny-list, because third-party plaintext
backends (`keyrings.alt.file.PlaintextKeyring`, etc.) cannot be enumerated in advance; anything not
explicitly recognised as secure is rejected.

### 11. `base64.b64decode(..., validate=True)`

Applied at `src/ot/config/secrets.py:137` (transparent decrypt) and `src/ottools/ot_secrets.py:318`
(rotate's decrypt-with-old-identity step). This rejects malformed base64 loudly (`binascii.Error`)
instead of silently accepting non-canonical input — robustness only, no behavior change for
well-formed `age1enc:` values produced by `encrypt()`/`set()`/`rotate()` themselves.

### 12. Missing-secret error string: name the secret and the setup path, at all three call sites

`packages/onetool-pack/src/otpack/http.py` — `api_headers()` (line 62), `require_api_key()` (line
148), `check_api_key()` (line 163) currently all format
`f"{secret_name} secret not configured"` (or the `"Error: "`-prefixed variant). Extend to:

```
f"Error: {secret_name} secret not configured. Set it in secrets.yaml "
f"(ot_secrets.set(key='{secret_name}', value='...') or the guided "
"'onetool init' secrets step)."
```

(Exact wording finalised during implementation; the requirement is that the string names the
secret **and** at least one concrete setup path — `secrets.yaml` and `ot_secrets.set()`/guided
`init` — not just the secret name.)

### 13. Proxy connect-error sanitization

`src/ot/proxy/manager.py:489,733` currently store `str(e)` verbatim. Add a small sanitizer
(reuse the existing log-redaction utility if `p22-technical-foundation`'s S3 redaction util has
already landed on `main` by implementation time; otherwise implement a minimal local sanitizer in
`manager.py` that strips `Authorization:`/`Bearer `/`Basic `-style substrings from the formatted
error before storing it in `self._errors[name]`) so a connect failure can never echo a decrypted
secret used as a bearer token, however unlikely.

## Risks / Trade-offs

- **[Risk] Flipping `encrypt()`/`rotate()` `backup` default to `False` is a breaking behavior
  change for any existing caller/script relying on the implicit `.bak`.** → Mitigation: called out
  as **BREAKING** in proposal.md; V3 is an explicit breaking-changes window per the maintainer
  ruling (no shim). The tool-secrets spec's MODIFIED requirements make the new default explicit
  and testable.
- **[Risk] The keyring backend allow-list could reject a legitimate secure backend not yet in the
  list (e.g. a future keyring release renames a backend class).** → Mitigation: the error message
  names the exact `module.Qualname` detected, making it a one-line addition to `_SECURE_BACKENDS`
  if a new legitimate backend needs allow-listing; this is a deliberate fail-closed design.
- **[Risk] `rotate()`'s "verify round-trip before persisting to keychain" adds a decrypt pass per
  value on top of the existing decrypt+encrypt, tripling crypto work for large secrets files.** →
  Mitigation: secrets files are small (typically single-digit to low-double-digit key counts);
  the correctness guarantee is worth the negligible extra CPU time.
- **[Risk] Converging the CLI `init` flow's extension list with `secrets.yaml` materialisation
  changes the checkbox choices users see, and existing scripts/docs referencing the old `_exts`
  list will be stale.** → Mitigation: this is exactly the "docs sweep" dependency called out in
  proposal.md Impact — `p18` should re-verify any doc screenshots/transcripts of the `init` flow
  after this change lands.
- **[Trade-off] `get()`'s "never return the value" invariant means an agent that legitimately
  needs to use a secret value programmatically (e.g. to paste into another tool's config) must use
  `out_file=` and then read that file with a separate tool call, rather than getting the value in
  one round trip.** → Accepted: this is the explicit hard requirement from the task brief; the
  two-step flow is the intended friction that prevents casual exfiltration into the transcript.

## Implementation guardrails

- No compatibility shims or aliases for the `backup=True`→`False` default flip, the required→
  optional `file=` signature changes, or any renamed/removed behavior. V3 is a breaking window:
  update the signature and the spec, do not add a transitional flag.
- No stubbing, no `TODO`-deferral. If an implementer hits a task that cannot be completed as
  specified (e.g. a keyring backend class name differs on the target platform from what Decision
  10 lists), stop and report the discrepancy rather than weakening the allow-list or silently
  skipping the validation.
- Every code task includes tests (`@pytest.mark.unit` at minimum; add `@pytest.mark.tools` where
  the existing `tests/ottools/unit/tools/test_secrets.py` convention already uses it). `just
  check` (lint + typecheck + test) must pass before any task is marked done.
- Any `rg` command listed in tasks.md's Verification section that is expected to return empty
  output MUST actually be run, and MUST return empty, before the corresponding task is checked
  off. "I edited the file" is not sufficient evidence — run the check.
- The `get()` no-plaintext-leak invariant is a hard requirement, not a default: do not add an
  `include_value=True` (or similarly named) escape hatch, even if it appears convenient during
  implementation.
