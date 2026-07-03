## 1. Keyring backend validation (foundation)

- [ ] 1.1 In `src/ottools/ot_secrets.py`, add `_SECURE_BACKENDS` (set of fully-qualified class
  name strings) and `_assert_secure_keyring_backend(kr: Any) -> None` per design.md Decision 10.
  Allow-list: `keyring.backends.macOS.Keyring`, `keyring.backends.Windows.WinVaultKeyring`,
  `keyring.backends.SecretService.Keyring`, `keyring.backends.libsecret.Keyring`,
  `keyring.backends.kwallet.DBusKeyring`, `keyring.backends.kwallet.DBusKeyringKWallet4`. Compute
  the qualname as `f"{type(kr.get_keyring()).__module__}.{type(kr.get_keyring()).__qualname__}"`.
  Raise/return an error naming the exact detected class on mismatch.
- [ ] 1.2 Call `_assert_secure_keyring_backend()` at the top of `init()` (`ot_secrets.py:68-103`,
  before any `keyring.set_password` at lines 94-96), `encrypt()` (`:106-182`, before the
  `keyring.get_password` at line 122), and `rotate()` (`:253-343`, before the
  `keyring.get_password` calls at lines 269-270).
- [ ] 1.3 Call `_assert_secure_keyring_backend()` in the transparent-decrypt path in
  `src/ot/config/secrets.py` (`load_secrets()`, before the `keyring.get_password("onetool",
  "age_identity")` call at line 127).
- [ ] 1.4 Unit test (`tests/ottools/unit/tools/test_secrets.py`, `@pytest.mark.unit
  @pytest.mark.tools`): mock `keyring.get_keyring()` to return an instance of
  `keyring.backends.fail.Keyring` (or a `MagicMock` with a non-allow-listed
  `type(...).__module__`/`__qualname__`) and assert `init()`, `encrypt()`, and `rotate()` all
  reject with an error naming the detected backend, and that no `set_password`/`get_password`
  call happens after rejection.
- [ ] 1.5 Unit test: mock a secure backend (e.g. a `MagicMock` whose `type(...).__module__` /
  `__qualname__` resolve to `"keyring.backends.macOS"` / `"Keyring"`) and assert `init()` succeeds
  normally (regression guard so the allow-list doesn't over-reject the happy path already covered
  by existing tests).
- [ ] 1.6 Unit test (`tests/unit/core/test_secrets.py`): mock an insecure backend for
  `load_secrets()`'s decrypt path and assert it raises before reading the identity.

## 2. Atomic write + 0600 helper (foundation)

- [ ] 2.1 In `src/ottools/ot_secrets.py`, add `_atomic_write_yaml(path: Path, data: dict) -> None`
  following the `tempfile.mkstemp` + `os.fdopen` + `Path(temp_path).replace(path)` idiom already
  used at `src/otutil/tools/file.py:1852-1870` (dump YAML with
  `default_flow_style=False, allow_unicode=True, sort_keys=False` to preserve key order per the
  existing "Key order preserved" scenarios). Call `os.chmod(temp_path, 0o600)` before the replace,
  and `os.chmod(path, 0o600)` again after (covers platforms where mkstemp perms aren't guaranteed
  0600). On any exception before the replace, unlink the temp file and re-raise.
- [ ] 2.2 Unit test: simulate a write failure (e.g. patch `yaml.dump` to raise mid-write) and
  assert the original `secrets.yaml` content is unchanged and no `.tmp_*` file is left behind.
- [ ] 2.3 Unit test: assert the file mode of a freshly written `secrets.yaml` is `0o600` even when
  the process umask is permissive (e.g. `os.umask(0o022)` in the test, verify resulting mode is
  still `0o600` not `0o644`).

## 3. `ot_secrets.py`: `init()` backend validation

- [ ] 3.1 Wire task 1.2's `init()` call per design.md Decision 10 (already covered by 1.2 — this
  task is the corresponding spec-scenario checkoff: "Insecure keyring backend rejected at init" in
  `openspec/specs/ottools/tool-secrets/spec.md` MODIFIED "Secrets Pack Identity Initialisation").
  Confirm existing `init()` scenarios (`Generate and store new identity`, `Identity already
  exists`, `Force overwrite`, `Default label`) still pass unmodified.

## 4. `ot_secrets.py`: `encrypt()` hardening

- [ ] 4.1 Change `encrypt()` signature default from `backup: bool = True` to `backup: bool = False`
  (`ot_secrets.py:106`).
- [ ] 4.2 Replace the unconditional `shutil.copy2(path, backup_path)` (`ot_secrets.py:148-151`)
  with: only run when `backup=True`, and `os.chmod(backup_path, 0o600)` immediately after the
  copy.
- [ ] 4.3 Replace the `with path.open("w") as f: yaml.dump(...)` write (`ot_secrets.py:171-172`)
  with a call to `_atomic_write_yaml()` from task 2.1.
- [ ] 4.4 Add the `_assert_secure_keyring_backend()` call from task 1.2 before line 122's
  `keyring.get_password`.
- [ ] 4.5 Unit test: `encrypt(file=...)` with no `backup=` argument — assert no `.bak` file is
  created and `result["backup"] is None`.
- [ ] 4.6 Unit test: `encrypt(file=..., backup=True)` — assert `.bak` is created at mode `0o600`.
- [ ] 4.7 Unit test: after `encrypt()`, assert `secrets.yaml`'s mode is `0o600`.
- [ ] 4.8 Update `tests/ottools/unit/tools/test_secrets.py`'s existing `encrypt()` tests that
  assumed `backup=True` default — add explicit `backup=True` where the test's intent was to
  verify backup behavior, so the default-flip doesn't silently break their assertions.

## 5. `ot_secrets.py`: `rotate()` hardening

- [ ] 5.1 Change `rotate()` signature default from `backup: bool = True` to `backup: bool = False`
  (`ot_secrets.py:253`).
- [ ] 5.2 Replace the unconditional `shutil.copy2` backup (`ot_secrets.py:296-299`) with the same
  `backup=True`-gated + `chmod(0o600)` pattern as task 4.2.
- [ ] 5.3 After re-encrypting each value with the new recipient (`ot_secrets.py:312-325`), add a
  round-trip verification step: decrypt each newly produced ciphertext with the **new** identity
  and assert it equals the original decrypted plaintext, before any write happens. Raise/return a
  clear internal error (not a silent skip) if verification fails for any key.
- [ ] 5.4 Replace the `with path.open("w") as f: yaml.dump(...)` write (`ot_secrets.py:327-328`)
  with `_atomic_write_yaml()` from task 2.1.
- [ ] 5.5 Reorder so the three `keyring.set_password` calls (`ot_secrets.py:330-332`, updating to
  the new identity) happen **only after** the atomic file write in 5.4 completes successfully —
  confirm this ordering already matches source order (write-then-keychain-update) and is preserved
  through the refactor; add a code comment noting the crash-safety invariant from design.md
  Decision 7.
- [ ] 5.6 Use `base64.b64decode(encoded, validate=True)` at `ot_secrets.py:318` instead of the
  current bare `base64.b64decode(encoded)`.
- [ ] 5.7 Add the `_assert_secure_keyring_backend()` call from task 1.2 before the
  `keyring.get_password` calls at `ot_secrets.py:269-270`.
- [ ] 5.8 Unit test: `rotate(file=...)` with no `backup=` argument — assert no `.bak` file.
- [ ] 5.9 Unit test: `rotate(file=..., backup=True)` — assert `.bak` created at `0o600`.
- [ ] 5.10 Unit test (crash simulation): patch the keychain update step (the third
  `keyring.set_password` call, or wrap all three) to raise after the atomic file write has
  already completed; assert the on-disk file now holds new-key ciphertext and the keychain still
  holds the old identity (simulating the crash window), then assert that calling `rotate()` again
  with the (unchanged) old identity fails with a clear decrypt-mismatch error rather than
  corrupting data further.
- [ ] 5.11 Unit test: patch the round-trip verification to detect a mismatch (e.g. force
  `pyrage.decrypt` to return a different value on the verification call) and assert `rotate()`
  aborts before writing the file or touching the keychain.
- [ ] 5.12 Update `tests/ottools/unit/tools/test_secrets.py`'s existing `rotate()` tests for the
  `backup=True` default flip, same as task 4.8.

## 6. `ot_secrets.py`: `file=` default resolution

- [ ] 6.1 Add `_resolve_secrets_file(file: str | None) -> Path` per design.md Decision 6: explicit
  `file` wins (expanduser); else `ot.config.loader.get_loaded_secrets_path()`; else
  `ot.paths.get_config_dir() / "secrets.yaml"`.
- [ ] 6.2 Change `encrypt()` (`ot_secrets.py:106`), `rotate()` (`:253`), and `audit()` (`:346`)
  signatures from `file: str` to `file: str | None = None`, resolving via 6.1 at the top of each
  function. `status()` (`:185`) already has `file: str | None = None` — route it through 6.1 too
  so its fallback behavior matches the other ops instead of just returning `None`/no-file mode.
- [ ] 6.3 Unit test: call `encrypt()` with no `file=` argument, with `ot.config.loader
  .get_loaded_secrets_path()` mocked to return a path — assert that path is used.
- [ ] 6.4 Unit test: call `encrypt()` with no `file=` argument and no loaded secrets path — assert
  it falls back to `<config dir>/secrets.yaml` (mock `get_config_dir()`).

## 7. `ot_secrets.py`: `set()`

- [ ] 7.1 Implement `set(*, key: str, value: str, file: str | None = None) -> dict[str, Any]` per
  design.md Decision 4: resolve file (6.1); validate backend (1.1) if identity present; if
  identity present, encrypt `value`, round-trip-verify (decrypt the produced ciphertext with the
  same identity and assert equality to `value`) before writing; if no identity, store plain value
  and add a `warning` field; write atomically at `0o600` via `_atomic_write_yaml()` (2.1); preserve
  key ordering (new keys appended, existing keys updated in place).
- [ ] 7.2 Add `"set"` to `__all__` in `ot_secrets.py:23`.
- [ ] 7.3 Unit test: `set(key="X", value="secret123")` with identity present — assert the written
  file has `age1enc:`-prefixed value for `X`, the return dict contains no `"secret123"` substring
  anywhere (`assert "secret123" not in json.dumps(result)`), and the file mode is `0o600`.
- [ ] 7.4 Unit test: `set()` overwriting an existing key — assert other keys/order unchanged.
- [ ] 7.5 Unit test: `set()` with no identity present — assert plain value stored and `warning`
  field present recommending `init()`/`encrypt()`.
- [ ] 7.6 Unit test: `set()` with an insecure keyring backend mocked — assert rejection before any
  file write (reuse the pattern from task 1.4).
- [ ] 7.7 Unit test: `set()` with no `file=` — assert default resolution per task 6.

## 8. `ot_secrets.py`: `get()`

- [ ] 8.1 Implement `get(*, key: str, file: str | None = None, out_file: str | None = None) ->
  dict[str, Any]` per design.md Decision 5: resolve file (6.1); look up `key` in the parsed YAML;
  if not found, return `{"found": False, "encrypted": None}`; if found and `out_file` is `None`,
  return `{"found": True, "encrypted": <bool>}` with no value field; if `out_file` is given,
  decrypt (if `age1enc:`-prefixed) or pass through (if plain), write the value to `out_file`,
  `os.chmod(out_file, 0o600)`, and return `{"found": True, "encrypted": <bool>, "written_to":
  out_file}` — still no value field.
- [ ] 8.2 Add `"get"` to `__all__` in `ot_secrets.py:23`.
- [ ] 8.3 Unit test: `get(key="X")` (no `out_file`) for an existing encrypted key — assert result
  is exactly `{"found": True, "encrypted": True, ...standard fields...}` with no value/ciphertext
  key present, using `assert "value" not in result` and a substring check against the known
  plaintext/ciphertext fixture value.
- [ ] 8.4 Unit test: `get(key="X", out_file=<tmp path>)` for an encrypted key — assert the tmp file
  contains the correct decrypted plaintext, is mode `0o600`, and the returned dict still has no
  value field (`assert <plaintext> not in json.dumps(result)`).
- [ ] 8.5 Unit test: `get(key="MISSING")` — assert `{"found": False, "encrypted": None}`
  (or the chosen equivalent shape) with no error raised.
- [ ] 8.6 Unit test: static/AST-level guard — assert `ot_secrets.get`'s source has no parameter
  whose name suggests a plaintext-inclusion escape hatch (e.g. assert `"include_value"` and
  `"reveal"` are not in `inspect.signature(ot_secrets.get).parameters`), documenting the "no
  escape hatch" invariant from design.md Decision 5 / Implementation guardrails as an executable
  check.

## 9. `src/ot/config/secrets.py` hardening

- [ ] 9.1 Use `base64.b64decode(encoded, validate=True)` at `config/secrets.py:137` instead of the
  current bare `base64.b64decode(encoded)`.
- [ ] 9.2 Align the "no identity" guidance text: pick one canonical message and apply it at both
  `config/secrets.py:129-132` (`SecretDecryptionError` message) and `ot_secrets.py:126`
  (`encrypt()`'s "no identity" error) — e.g. both use `"No age identity found in the OS keychain.
  Run ot_secrets.init() to generate one."` Also check `ot_secrets.py:276` (`rotate()`'s "no
  identity" message) for the same drift and align it too.
- [ ] 9.3 Unit test (`tests/unit/core/test_secrets.py`): assert `load_secrets()` raises
  `SecretDecryptionError` with the new canonical message text when no identity is present.
- [ ] 9.4 Unit test: assert malformed (non-canonical) base64 in an `age1enc:` value raises a clear
  decode error from `load_secrets()` rather than being silently accepted.

## 10. `packages/onetool-pack/src/otpack/http.py`: missing-key error string

- [ ] 10.1 Extend the error string in `api_headers()` (`http.py:62`,
  `raise ValueError(f"{secret_name} secret not configured")`) to name both the secret and a
  concrete setup path (`secrets.yaml`, `ot_secrets.set()`, or the guided `onetool init` secrets
  step) per design.md Decision 12.
- [ ] 10.2 Extend the error string in `require_api_key()` (`http.py:148`) the same way.
- [ ] 10.3 Extend the error string in `check_api_key()` (`http.py:163`) the same way.
- [ ] 10.4 Unit/integration test covering all three functions: assert the error message contains
  the secret name AND at least one of `"secrets.yaml"`, `"ot_secrets.set"`, or `"onetool init"`.
- [ ] 10.5 `rg -n '"secret not configured"' packages/onetool-pack/src/otpack/http.py` — confirm all
  three occurrences now include the extended guidance (manually inspect, since the base string
  substring will still match; the check is that no occurrence is the bare
  `f"{secret_name} secret not configured"` with nothing appended).

## 11. `src/ot/proxy/manager.py`: sanitize connect-error strings

- [ ] 11.1 Add a small sanitizer (e.g. `_sanitize_connect_error(msg: str) -> str`) that strips/
  redacts `Authorization:`/`Bearer `/`Basic `-prefixed substrings from a formatted exception
  string. If `p22-technical-foundation`'s S3 log-redaction utility has already landed on `main` at
  implementation time, reuse it instead of writing a new one; otherwise implement locally in
  `manager.py`.
- [ ] 11.2 Apply the sanitizer at `manager.py:489` (`self._errors[name] = str(e)` in the
  startup/parallel-connect path) and `manager.py:733` (`self._errors[name] = str(e)` in
  `connect_additional`).
- [ ] 11.3 Unit test (`tests/unit/core/test_proxy_manager.py`): simulate a connection exception
  whose `str()` contains `"Authorization: Bearer sk-secret123"` and assert the stored
  `self._errors[name]` value does not contain `"sk-secret123"` while still containing enough
  context to diagnose the failure (e.g. "connection failed" or the exception type name).

## 12. CLI TUI: masked value entry primitive

- [ ] 12.1 Add `ask_password_sync(prompt: str) -> str | None` to `src/ot/_tui.py`, following the
  exact shape of `ask_text_sync()` (line 72): wrap `questionary.password(prompt,
  style=APP_STYLE).ask()` in `try/except KeyboardInterrupt: return None`.
- [ ] 12.2 Unit test: mock `questionary.password(...).ask()` to return a value, assert
  `ask_password_sync` returns it; mock it to raise `KeyboardInterrupt`, assert `None` is returned.

## 13. CLI: `onetool init` secrets step

- [ ] 13.1 Add `"secrets.yaml"` to the `_exts` list in `src/onetool/cli.py:440-446`, with a
  description (e.g. `("secrets.yaml", "API keys / credentials (optionally encrypted)")`).
- [ ] 13.2 In `init_callback()` (`cli.py:382-480`), when `"secrets.yaml"` is among `selected_ext`,
  materialise it via `_copy_file(ot_dir, "secrets.yaml")` (existing helper, `cli.py:330`) — same
  as any other extension — but exclude it from the `includes` list passed to
  `_write_onetool_yaml()` (`cli.py:471`), per the "never in `include:`" rule in
  `openspec/specs/onetool-cli/spec.md`.
- [ ] 13.3 After materialising `secrets.yaml`, if it was selected, prompt "Set up encrypted
  secrets?" (`questionary.confirm(..., default=False)`, matching the existing overwrite-confirm
  pattern at `cli.py:432-434`).
- [ ] 13.4 If confirmed, loop: prompt for `key` via `ask_text_sync` (empty key stops the loop),
  then `value` via the new `ask_password_sync` (task 12.1); write each pair into the materialised
  `secrets.yaml` (read-modify-write the YAML, preserving the template's existing structure/
  comments as best-effort — at minimum preserve any already-present keys).
- [ ] 13.5 After the loop (if at least one pair was entered and not cancelled), call
  `ottools.ot_secrets.init()` in-process (handle "already exists" by prompting whether to reuse or
  pass `force=True`), then `ottools.ot_secrets.encrypt(file=<secrets.yaml path>, backup=False)`,
  then `ottools.ot_secrets.audit(file=<secrets.yaml path>)` and assert `safe is True` before
  printing success; if `safe` is `False` after `encrypt()`, print a clear failure message (this
  indicates a bug in the flow, per design.md Decision 2 — do not report success).
- [ ] 13.6 Handle Ctrl+C during key/value entry per the "Cancel during encrypted-secrets key/value
  entry" scenario: stop the loop, do not call `init()`/`encrypt()`, print a message telling the
  user `secrets.yaml` has unencrypted values pending `ot_secrets.encrypt()`.
- [ ] 13.7 Unit/integration test (`tests/unit/core/test_init_redesign.py`): select `secrets.yaml`
  without the encrypted-secrets step — assert `secrets.yaml` is created at mode `0o600` and is NOT
  present in the written `onetool.yaml`'s `include:` list.
- [ ] 13.8 Unit/integration test: select `secrets.yaml`, confirm "Set up encrypted secrets?", enter
  one key/value pair, mock `ot_secrets.init()`/`encrypt()`/`audit()` — assert `init()` and
  `encrypt(backup=False)` were called with the expected file path, and that the flow reports
  success only when `audit()` reports `safe: True`.
- [ ] 13.9 Integration test (no mocks, using a real ephemeral keychain fixture if one exists in the
  test suite, or skipped/marked if the CI environment has no usable keyring backend): run the full
  init flow end-to-end with one key/value pair entered, then read the resulting `secrets.yaml` off
  disk and assert **no line contains the entered plaintext value** — this is the "clean machine
  leaves no plaintext on disk" acceptance check from the report, executed as a test rather than
  only a manual check.

## 14. Docs

- [ ] 14.1 Update the "Requires" section of `docs/reference/tools/ot_secrets.md:33-35` to list
  `pyrage` and `keyring` as Python package dependencies alongside the existing OS keychain support
  bullet.
- [ ] 14.2 Update the "Functions" table in `docs/reference/tools/ot_secrets.md` (around lines
  17-23) to add `ot_secrets.set(key, value, file)` and `ot_secrets.get(key, file, out_file)` rows,
  and update the `encrypt`/`status`/`rotate`/`audit` rows' `file` parameter description to note it
  now defaults to the configured secrets path.
- [ ] 14.3 Update the "Key Parameters" table's `backup` row (around line 30) to reflect the new
  `False` default.

## 15. Verification

- [ ] 15.1 `rg -n "backup: bool = True" src/ottools/ot_secrets.py` — MUST return empty (both
  `encrypt()` and `rotate()` now default `backup=False`).
- [ ] 15.2 `rg -n '"set", "status"' src/ottools/ot_secrets.py` or equivalent manual check —
  confirm `__all__` at `ot_secrets.py:23` includes `"get"` and `"set"` alongside the existing
  five names.
- [ ] 15.3 `rg -n "shutil.copy2" src/ottools/ot_secrets.py` — every remaining call site MUST be
  inside a `if backup:` conditional followed by a `chmod(..., 0o600)` (manual inspection of each
  match, not just an empty-output check).
- [ ] 15.4 `rg -n "path.open\(.w.\)" src/ottools/ot_secrets.py` — MUST return empty for the
  `encrypt`/`rotate`/`set` write paths (all writes now go through `_atomic_write_yaml`).
- [ ] 15.5 `rg -n "b64decode\(encoded\)$" src/ottools/ot_secrets.py src/ot/config/secrets.py` —
  MUST return empty (both call sites now pass `validate=True`).
- [ ] 15.6 `rg -n 'secret not configured"' packages/onetool-pack/src/otpack/http.py` — inspect all
  three matches (lines 62, 148, 163) and confirm each includes setup guidance beyond the bare
  secret name.
- [ ] 15.7 No standalone `rg` check applies here — verify via test 13.7 (asserting
  `secrets.yaml` is absent from the written `onetool.yaml`'s `include:` block) that the
  materialised extensions list and the `include:` list have diverged correctly for the
  `secrets.yaml` special case.
- [ ] 15.8 `uv run pytest tests/ottools/unit/tools/test_secrets.py -m "unit and tools" -v` — all
  pass, including new `set`/`get`/backend-validation/atomic-write/rotate-crash-simulation tests.
- [ ] 15.9 `uv run pytest tests/unit/core/test_secrets.py -m unit -v` — all pass, including the new
  base64-strict and guidance-message tests.
- [ ] 15.10 `uv run pytest tests/unit/core/test_init_redesign.py -m unit -v` — all pass, including
  the new secrets-step tests.
- [ ] 15.11 `uv run pytest tests/unit/core/test_proxy_manager.py -m unit -v` — all pass, including
  the new connect-error sanitization test.
- [ ] 15.12 `just check` — lint (ruff) + typecheck (mypy strict) + full test suite all pass.
- [ ] 15.13 Manual clean-machine walkthrough (acceptance check from the report): on a machine/venv
  with no prior `secrets.yaml` and no prior keychain identity, run `onetool init`, select
  `secrets.yaml`, confirm "Set up encrypted secrets?", enter one key/value pair, finish the flow,
  then `cat` the resulting `secrets.yaml` and confirm the entered value only ever appears as an
  `age1enc:`-prefixed ciphertext, never as plaintext, and that no `.bak` file exists in the config
  dir.
- [ ] 15.14 Manual missing-key check: call a key-gated pack function (e.g. a `brave` search tool)
  with `BRAVE_API_KEY` unset, and confirm the returned error message names `BRAVE_API_KEY` **and**
  a concrete setup command/path.
