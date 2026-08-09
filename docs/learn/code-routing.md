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
or environment, credential presence without its value, live model count, IDs,
and provider values reported by CLIProxyAPI, the derived management URL and
reachability, and detected `cliproxyapi`, `claude`, and `codex` executable
versions. Required inference failures exit non-zero while independent checks
continue; missing executables or an unavailable management page are warnings.

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

Choose Claude or Codex, select an exact model ID from the case-insensitively
alphabetized current CLIProxyAPI inventory, and then select an explicit context
policy. After valid selections, OneTool prints a shell-safe command such as
`onetool code claude --context 1m -- gpt-5.6-sol` for direct reuse before
launching the harness. The displayed command contains no credentials or internal
provider overrides. Cancellation returns without launching. A bare command in a
non-interactive environment fails instead of waiting for input.

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

Every token after `MODEL` is appended unchanged and in order. A separator is not
required for ordinary model IDs; use `--` immediately before a full ID that
starts with `-`. A literal `--` after `MODEL` is preserved. Launcher-owned
options must appear before `MODEL`; therefore `--context` after `MODEL` is
forwarded to the official harness unchanged.

## Understand Harness Model Selectors

For Claude Code, OneTool supplies the selected proxy model through both
`ANTHROPIC_MODEL` and `claude --model`, and keeps
`CLAUDE_CODE_SUBAGENT_MODEL` aligned. Inherited Opus, Sonnet, and Haiku default
overrides are removed without replacements, so the selected proxy model appears
as the custom/default model instead of being duplicated across Claude family
slots.

For Codex CLI, OneTool keeps the proxy provider and resolved `--model` selection
invocation-scoped. Immediately before launch it displays the resolved proxy model
and explains that Codex `/model` shows Codex's bundled native catalog. Change the
proxy model by launching again through `onetool code`; the native catalog does
not replace OneTool's live pre-launch selection. Invocation-scoped means the proxy
provider and model apply to every new, resumed, or forked session opened in that
Codex process. Launch plain `codex` instead when a saved session must retain its
native model.

Codex can report that MCP startup was interrupted while replacing an initial
server startup pass with a runtime refresh. Wait for the refresh, then use `/mcp`
to inspect the final server state. A server missing from that final inventory is
an actionable failure; the earlier interrupted-pass message alone is not.

Codex App remains native-model-only for this integration. Launch custom
CLIProxyAPI models through Codex CLI. OneTool does not generate or write model
catalogs, profiles, aliases, harness configuration, or settings files for either
client.

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

This command performs one authenticated, bounded inventory request and prints a
`MODEL` and `PROVIDER` table. Rows are sorted case-insensitively by the complete
model ID, including any configured prefix. `PROVIDER` uses the response's
optional `owned_by` value and displays `-` when unavailable; OneTool does not
infer it from the ID or prefix. The command does not cache or otherwise classify
the inventory.

For native or direct-provider use, invoke `claude` or `codex` normally instead of
using the OneTool launcher.

Installed-client capability checks remain opt-in and non-billable:

```bash
ONETOOL_LIVE_CODE_CLIENTS=confirmed \
  uv run pytest tests/integration/core/test_code_harnesses.py
```
