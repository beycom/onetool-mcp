# Code harness routing

OneTool can launch Claude Code and Codex through explicit configured routes. It is a
thin foreground launcher: it resolves a model and route, validates required
capabilities, constructs invocation-scoped arguments and environment changes, and
runs the official client with the terminal attached.

OneTool configures and launches the selected route. It does not guarantee provider
compatibility, terms compliance, model availability, subscription classification,
included usage, rate limits, or billing treatment. The user is responsible for the
selected configuration; CLIProxyAPI owns proxy authentication and provider routing.

## Quick start

Install the official Claude Code or Codex client you intend to launch, then create
the routing fragment beside an existing OneTool configuration:

```bash
onetool code setup --config .onetool/onetool.yaml
```

Add the generated fragment to `.onetool/onetool.yaml`:

```yaml
include:
  - code-routing.yaml
```

Review `.onetool/code-routing.yaml` before use. It contains the shared model
registry, native and disabled optional harness routes, the external CLIProxyAPI
inference connection, a default CLIProxyAPI generation route, and an independent
embedding route. Remove sections you do not use, update executable and user-owned
file paths, and put any selected route's named secret in the adjacent
`.onetool/secrets.yaml`.

Inspect the effective setup without launching a client:

```bash
onetool code models
onetool code status
onetool code doctor
onetool claude --dry-run --verbose
onetool codex --dry-run --verbose
```

Launch a configured default or select an explicit model and route:

```bash
onetool claude
onetool codex
onetool codex sol --route codex-sol-proxy
onetool claude -- --continue
```

Arguments after `--` are passed to the official client in order. Use `--config`
and `--secrets` when the files are not in the current project's `.onetool`
directory. Native routes use the client's own authentication; proxy and direct
provider routes require their explicitly configured external service and secret.

## Ownership boundary

OneTool does not install, configure, start, stop, restart, or administer CLIProxyAPI.
It does not read CLIProxyAPI OAuth files, accounts, logs, retries, routing policy, or
management endpoints. A proxied route uses only an explicitly configured inference
base URL, named inference-client secret, bounded model discovery, and a supported
client adapter.

Claude and Codex settings, profiles, catalogs, authentication, and CLIProxyAPI
configuration remain user-owned. OneTool passes checked paths to supported clients
but does not parse, generate, merge, or rewrite those files.

## Supported routes

| Harness | Provider source | Transport | Default posture |
|---|---|---|---|
| Claude Code | Claude subscription | direct | Recommended native default |
| Claude Code | Claude subscription | CLIProxyAPI | Disabled by default |
| Claude Code | Codex subscription | CLIProxyAPI | Explicit route |
| Claude Code | OpenRouter | CLIProxyAPI | Explicit route |
| Codex | Codex subscription | direct | Recommended native default |
| Codex | Codex subscription | CLIProxyAPI | Optional explicit route |
| Codex | OpenRouter | direct custom provider | Explicit route |

Routes outside this table are rejected. OneTool never substitutes another model,
provider, transport, or billing path.

Proxying a Claude consumer subscription through CLIProxyAPI is not an approved
Anthropic subscription path and may breach Anthropic's terms, result in account
restrictions, or change billing treatment. Use it at your own risk. The route must
be explicitly enabled and this warning is shown on every launch.

## External configuration references

Verify behavior against the installed client versions before enabling a route:

- Codex: [basic configuration](https://developers.openai.com/codex/config-basic/),
  [advanced configuration](https://developers.openai.com/codex/config-advanced/),
  [configuration reference](https://developers.openai.com/codex/config-reference/),
  and [CLI reference](https://developers.openai.com/codex/cli/reference/).
  The change's verified upstream baseline also records the corresponding current
  client documentation surfaces for [basic configuration](https://learn.chatgpt.com/docs/config-file/config-basic),
  [advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced),
  [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference),
  and [developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli).
- Claude Code: [settings](https://code.claude.com/docs/en/settings),
  [CLI reference](https://code.claude.com/docs/en/cli-usage),
  [model configuration](https://code.claude.com/docs/en/model-config), and
  [LLM gateway configuration](https://code.claude.com/docs/en/llm-gateway).
- CLIProxyAPI: [configuration options](https://help.router-for.me/configuration/options),
  [canonical example](https://github.com/router-for-me/CLIProxyAPI/blob/main/config.example.yaml),
  [Codex client guide](https://help.router-for.me/agent-client/codex), and
  [Claude Code client guide](https://help.router-for.me/agent-client/claude-code).

Development capability provenance is recorded in
`tests/fixtures/harness_routing/capabilities.yaml`. Those exact observed versions are
test provenance, not runtime pins.

## Manual live-route checklist

Live inference can consume subscription allowance, provider credits, or paid API
usage. Before each check, inspect the effective route with `--dry-run --verbose`,
confirm the endpoint and model, and obtain explicit confirmation from the person
responsible for the account. Never automate these checks in the default test suite.

- [ ] Claude Code with a native Claude subscription: confirm the account owner
  approves one interactive request, then verify native auth and exit propagation.
- [ ] Claude Code with a Claude subscription through CLIProxyAPI: confirm the owner
  accepts the displayed Anthropic terms/account/billing warning before one request.
- [ ] Claude Code with a Codex subscription through CLIProxyAPI: confirm allowance
  use, verify the discovered alias, then send one bounded request.
- [ ] Claude Code with OpenRouter through CLIProxyAPI: confirm the selected
  OpenRouter route may incur charges before one bounded request.
- [ ] Codex with a native Codex subscription: confirm the account owner approves one
  interactive request and verify no custom provider override is present.
- [ ] Codex with a Codex subscription through CLIProxyAPI: confirm allowance use and
  verify Responses-compatible routing before one bounded request.
- [ ] Codex with direct OpenRouter: confirm the named API credential and potential
  charges before one bounded request.

Installed-client capability checks are separately opt-in and non-billable:

```bash
ONETOOL_LIVE_CODE_CLIENTS=confirmed \
  uv run pytest tests/integration/core/test_code_harnesses.py
```
