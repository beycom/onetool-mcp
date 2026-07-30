# Code harness routing

OneTool launches Claude Code and Codex from exact local routing records. A target
is either:

- a proxy route through an independently managed CLIProxyAPI service; or
- a direct, user-owned Codex profile.

Normal launch and dry run use only local configuration, executable resolution, and
the selected target's credential boundary. They do not call `/v1/models`, read
Claude/Codex settings, or manage CLIProxyAPI.

## Install the template

Run interactive initialization and select `code-routing.yaml`:

```bash
onetool init
```

The standard initializer copies the template, backs up a conflicting file, and
adds it to `onetool.yaml`'s `include` list. There is no separate `code setup`
command.

## Proxy routes

```yaml
code:
  default:
    model: gpt-5.6-sol
    route: codex_subscription

  proxy:
    base_url: http://127.0.0.1:8317
    secret_name: CLIPROXY_INFERENCE_KEY
    connect_timeout: 2
    request_timeout: 5
    routes:
      codex_subscription:
        - id: gpt-5.6-sol
          shortcut: sol
          label: GPT-5.6 Sol

      openrouter:
        - id: z-ai/glm-5.2
          shortcut: glm
          claude:
            context: 1m
            auto_compact_window: 900000

      claude_subscription:
        - id: claude-sonnet-4-6
          shortcut: sonnet
          claude:
            context: standard
```

Route names are exact. Claude supports `claude_subscription`,
`codex_subscription`, and `openrouter`; Codex supports `codex_subscription` and
`openrouter`.

The proxy inference key belongs in `secrets.yaml`:

```yaml
CLIPROXY_INFERENCE_KEY: your-inference-key
```

Proxying a Claude consumer subscription is opt-in and may breach Anthropic's terms,
affect the account, or change billing. OneTool displays that warning on every
`claude_subscription` launch, including quiet mode.

## Direct Codex profiles

A direct profile delegates provider URL, catalog, and credential handling to Codex:

```yaml
code:
  default:
    model: z-ai/glm-5.2
    profile: openrouter

  direct:
    codex:
      profiles:
        openrouter:
          - id: z-ai/glm-5.2
            shortcut: glm

  clients:
    codex:
      additional_arguments: [--search]
```

Launch it explicitly:

```bash
onetool codex glm --profile openrouter
onetool codex z-ai/glm-5.2 -p openrouter
```

The resulting owned arguments are `codex --profile openrouter --model
z-ai/glm-5.2`. OneTool does not add its proxy provider, base URL, or inference
secret. `--profile` and `--route` are mutually exclusive, and direct profiles are
never offered to Claude.

## Model identity

Launcher records accept:

- required exact `id`;
- optional exact `shortcut`;
- optional presentation-only `label`;
- optional operational Claude policy.

Selection accepts only an exact id or exact shortcut. It is case-sensitive and
does not normalize separators or perform substring matching. Shortcuts must be
globally unique. If the same id appears under multiple targets, supply the exact
`--route` or `--profile`.

The top-level `models` registry is generation-only. Launcher records intentionally
do not accept generation modalities, interfaces, structured-output modes, efforts,
or aliases.

## Claude context policy

`claude.context: 1m` changes the effective Claude selector to `<id>[1m]`.
`auto_compact_window` is optional, positive, and below 1,000,000. It sets
`CLAUDE_CODE_AUTO_COMPACT_WINDOW` only for the launched process.

`claude.context: standard` keeps the base id and sets
`CLAUDE_CODE_DISABLE_1M_CONTEXT=1`. When the policy is absent, OneTool keeps the
base id and clears inherited context overrides.

OneTool also clears conflicting inherited Anthropic gateway, model, model-name,
model-description, and context variables before applying the selected proxy
environment. The policy is not inferred from model names or generation metadata.

## Clients and permissions

```yaml
code:
  permission: normal  # normal | bypass

  clients:
    claude:
      executable: claude
      working_directory: /path/to/project
      additional_arguments: [--no-chrome]

    codex:
      executable: codex
      working_directory: /path/to/project
      home_path: /path/to/codex-home
      additional_arguments: [--search]

  presentation:
    quiet: false
    verbose: false
```

Working directories and `CODEX_HOME` apply only to the launched process. User
files are never rewritten.

Everything after the first real `--` remains an ordered harness tail:

```bash
onetool codex sol -- exec --json
onetool claude sonnet -- plugins
```

OneTool preserves the tail but rejects launcher-owned conflicts. For Codex these
include `--model`/`-m`, `--profile`/`-p`, `--config`/`-c`, `--oss`, and the
permission bypass flag. Long options with `=` and short options in separated or
attached form, such as `-m value` and `-mvalue`, are rejected consistently.

## Process handoff and diagnostics

After validation and optional presentation, OneTool changes to the configured
working directory and replaces itself with the harness process. The harness
naturally owns the terminal, signals, and exit status; OneTool does not supervise a
child or print a post-exit summary.

Dry run returns before process replacement:

```bash
onetool codex glm --profile openrouter --dry-run --verbose
```

The output identifies target kind/name, exact model, argv shape, and environment
key changes without values.

Diagnostic commands are:

```bash
onetool code models
onetool code status
onetool code doctor
onetool code config
```

`status` is local-only and reports only configured harnesses and targets. `doctor`
runs one bounded `--help` probe per configured harness. When proxy routes and their
named secret are available, it also calls `/v1/models` exactly once and compares
configured proxy ids exactly. A missing proxy secret is reported without making
that request. Direct-only diagnostics do not resolve a proxy secret or call the
proxy.

## Ownership boundary

OneTool never installs, configures, starts, stops, authenticates, or administers
CLIProxyAPI. It never reads or rewrites CLIProxyAPI, Claude, or Codex configuration,
profile, catalog, OAuth, or authentication files.

- [Claude model configuration](https://code.claude.com/docs/en/model-config)
- [Claude environment variables](https://code.claude.com/docs/en/env-vars)
- [Codex configuration](https://developers.openai.com/codex/config-basic/)
- [CLIProxyAPI configuration](https://help.router-for.me/configuration/options)

Installed-client capability checks are opt-in and non-billable:

```bash
ONETOOL_LIVE_CODE_CLIENTS=confirmed \
  uv run pytest tests/integration/core/test_code_harnesses.py
```
