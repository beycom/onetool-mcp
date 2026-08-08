# Code Harness Launchers

OneTool can replace itself with the official Claude Code or Codex executable and
route that harness through an independently managed CLIProxyAPI service.
CLIProxyAPI owns provider accounts, authentication, its live model inventory,
and upstream routing; OneTool supplies model selection and invocation-scoped
harness settings.

## Environment

Set the launcher credential in the process environment:

```bash
export CLIPROXY_INFERENCE_KEY="your-inference-client-key"
export CLIPROXY_BASE_URL="http://127.0.0.1:8317"  # optional default
```

`CLIPROXY_BASE_URL` is the proxy origin, without `/v1`. The launcher does not
read `onetool.yaml`, `secrets.yaml`, the current directory, or CLIProxyAPI's
internal files. In a source checkout, prefix the examples below with `uv run`.

## Check Readiness

```bash
onetool code status
```

Status displays the normalized proxy origin and whether it came from the default
or environment, credential presence without its value, live model count and IDs,
the derived management URL and reachability, and detected `cliproxyapi`, `claude`,
and `codex` executable versions. Required inference failures exit non-zero while
independent checks continue; missing executables or an unavailable management
page are warnings.

To display status and then open the derived management page in the platform
browser:

```bash
onetool code status --open
```

Plain `status` never opens a browser. OneTool does not read a management key or
proxy YAML, call management APIs, perform login or OAuth, manage the proxy
service, or write user files.

## Select Interactively

Run the group without a subcommand in an interactive terminal:

```bash
onetool code
```

Choose Claude or Codex, search the current CLIProxyAPI model inventory, and then
select an explicit context policy. Cancellation returns without launching. A
bare command in a non-interactive environment fails instead of waiting for
input.

## Launch Directly

Supply a full model ID or an unambiguous shorthand:

```bash
onetool code claude sol --continue
onetool code codex --context 200000 glm52 exec --full-auto
```

Each launch performs one authenticated, bounded `GET /v1/models` request. An
exact case-sensitive ID wins first, followed by a case-insensitive exact match,
then a unique case-insensitive token, suffix, or substring match. For example,
`sol` can select `gpt-5.6-sol` when it is the only match. Ambiguous queries fail
with the candidate IDs, and missing queries fail without substituting a model.
There is no static catalog, compatibility alias, route, profile, provider, or
capability registry.

Every token after `MODEL` is appended unchanged and in order. No `--` separator
is required, and a literal `--` is preserved. Launcher-owned options must appear
before `MODEL`; therefore `--context` after `MODEL` is forwarded to the official
harness unchanged.

## Set Context Explicitly

Context defaults to `auto`. Put `--context` before `MODEL`:

```bash
onetool code claude --context 1m gpt-5.6-sol
onetool code claude --context 200k gpt-5.6-sol
onetool code codex --context 1000000 gpt-5.6-sol
```

Claude accepts only `auto`, `200k`, and `1m`. `1m` generates the Claude selector
`<model>[1m]`; `200k` keeps the base ID and sets
`CLAUDE_CODE_DISABLE_1M_CONTEXT=1` for the child. Codex accepts `auto`, `200k`,
`1m`, or any positive integer token count. A numeric Codex context generates
invocation-scoped `model_context_window` and a 90-percent
`model_auto_compact_token_limit`. No context choice modifies a settings file.

## List Model IDs

```bash
onetool code models
```

This command performs one authenticated, bounded inventory request and prints
only the direct IDs returned by CLIProxyAPI. It does not cache or classify the
inventory.

For native or direct-provider use, invoke `claude` or `codex` normally instead of
using the OneTool launcher.

Installed-client capability checks remain opt-in and non-billable:

```bash
ONETOOL_LIVE_CODE_CLIENTS=confirmed \
  uv run pytest tests/integration/core/test_code_harnesses.py
```
