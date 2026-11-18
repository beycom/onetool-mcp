# Upstream servers

Ingress is stdio. Upstreams use stdio or Streamable HTTP. OneTool does not provide a remote ingress listener or a multi-user service.

Copy a server's documented command/args or URL/headers into a named YAML entry. The keys follow common `mcpServers` conventions; OneTool validates them before handing them to FastMCP's canonical config conversion. See the [configuration reference](config.md).

Connections are lazy. Discovery or an authenticated tool operation can connect; status and config validation do not. An unavailable server does not disable healthy servers. When tools are missing from search, inspect `onetool_status`.

## Local fixtures

[examples/fixtures.yaml](../examples/fixtures.yaml) runs the owned stdio fixture twice as alpha and beta. To try HTTP, start the same fixture from the checkout:

```sh
uv run python tests/fixtures/fixture_server.py --transport http --port 8765
```

Use the loopback HTTP example in [config.md](config.md#environment-references), with `FIXTURE_TOKEN` set in the gateway's environment. Stop the fixture when finished. The test suite starts and stops its own HTTP fixture on an available loopback port.

OneTool retains a supported stateful client per server and gateway ingress connection. Native upstream code handles connection setup, callback context and process cleanup. Calls to the same fixture backend were safe under concurrency; there is no owned connection manager or worker pool.

## Authentication

Use explicit headers or upstream OAuth. Store credential values in an explicit `--secrets PATH` file and reference `${NAME}` in headers or env; see [secrets](config.md#secrets). OneTool never copies caller credentials into an upstream request automatically.

OAuth tokens go through FastMCP's `token_storage` argument to upstream KeyringStore. OneTool requires a secure macOS, Windows, SecretService or KWallet backend. A keyring chain is accepted only when every child is secure. Select a supported system backend if your default chain includes plaintext storage.

No plaintext fallback exists. If secure storage is unavailable, that server reports an auth error while unauthenticated servers remain usable. The OAuth browser can open during discovery or a tool operation, never during config validation. A real browser login remains an owner release check for this candidate.

Upstream KeyringStore has a 2,560-byte value limit on Windows. Oversized token records fail; OneTool does not implement a chunk store. Other-platform installation and OAuth behavior have not been exercised by the macOS candidate proof.

## Curation and help

Use per-server descriptions and instructions to explain intended use. Tool descriptions, hidden defaults and tag filters use native FastMCP transforms, before namespace collision checks. Curation is descriptive and does not grant authorization. Call `help(query="alpha", detail="full")` for connected native instructions followed by configured guidance, tools, resources and prompts. Lazy and disabled servers remain visible; help suggests `onetool_servers(action="enable", name="alpha")` rather than connecting them implicitly.

## Older OneTool packs

The last published release before V4 is `onetool-mcp==2.2.2`. Its executable is `onetool`. Run it as an ordinary upstream:

```yaml
version: 4
servers:
  v3:
    transport: stdio
    command: uvx
    args: [--from, onetool-mcp==2.2.2, onetool, --config, /absolute/path/to/v3.yaml]
```

That upstream owns its old config and pack API. V4 owns neither. Native discovery returns `v3_run`; inspect its schema before calling. The bridge proof uses a separate temporary V3 config with `version: 2` and `tools_dir: []`, then calls its timer pack through CodeMode. Backend clients explicitly negotiate with `mode="auto"`; no protocol setting is needed in YAML.

Use a direct client connection for servers whose value is image/binary output, or when a client needs callback behavior beyond the locally tested progress forwarding. See [FastMCP proxy behavior](https://gofastmcp.com/docs/servers/providers/proxy).
