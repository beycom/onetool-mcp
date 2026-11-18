# OneTool V4

OneTool is a local MCP gateway. Configure upstream servers in one YAML file, then use Python to chain their tools through FastMCP CodeMode. Intermediate values stay inside the execution; `return` selects the answer.

4.0.0rc1 is a local release candidate. It has not been published. A real OAuth login and a week of daily use remain release checks.

## Install the candidate

From this checkout, build the wheel and install it with the uv installer. The script downloads uv and a managed Python 3.12, so it needs network access but no separately installed Python.

```sh
just install-locked
just build
sh scripts/install.sh dist/onetool_mcp-4.0.0rc1-py3-none-any.whl
```

The tested installer target is macOS arm64. The pure Python wheel is the package format for other platforms; their installer and live OAuth checks remain unverified. The script installs into `$HOME/.local/bin` and does not edit your PATH. Add that directory to your client environment.

## Try the fixture servers

The checkout includes two deterministic servers in [examples/fixtures.yaml](examples/fixtures.yaml). Validate the file:

```sh
uv run onetool --version
uv run onetool check-config --config examples/fixtures.yaml
```

Configure your MCP client to run `uv run onetool serve --config /absolute/path/to/examples/fixtures.yaml` from this checkout. For an installed upstream, use its documented command and arguments. A minimal server entry is:

```yaml
version: 4
servers:
  alpha:
    transport: stdio
    command: python
    args: [tests/fixtures/fixture_server.py]
    cwd: ..
```

That example belongs in the checkout's `examples/` directory. Paths in arguments remain literal; `cwd` resolves from the config directory.

Use `search` to find `alpha_add` and `beta_add`, then `get_schema` to inspect their parameters. Pass this Python as `execute`'s `code` argument:

```python
left = await call_tool("alpha_add", {"a": 2, "b": 3})
right = await call_tool("beta_add", {"a": 4, "b": 5})
return await call_tool("alpha_add", {"a": left["value"], "b": right["value"]})
```

The result is `{"value": 14}`. Python variables last for one execution; upstream state can last for the gateway process.

Read [configuration](docs/config.md), [Python usage](docs/python.md), [server setup](docs/servers.md) and [troubleshooting](docs/troubleshooting.md). Developers can start with [architecture](dev/architecture.md), [testing](dev/testing.md), [releases](dev/release.md) and [worktrees](dev/worktrees.md).

V4 owns no packs. Run a pinned older OneTool release as an ordinary upstream if you need its packs. The old implementation remains at the local `archive/pre-v4-main` branch. See [the new changelog](CHANGELOG.md) for the 4.0 boundary.
