# Testing

Install locked dependencies, then use the project recipes:

```sh
just install-locked
just test
just lint
just check
```

`just check` runs ruff/format, strict mypy and the tests. During a batch, run the focused files first, then one full check. Rerun a full gate after a failure or relevant change. Keep inputs fixed while it runs.

`tests/fixtures/fixture_server.py` is the same module used in the private POCs. It serves stdio or loopback HTTP. Tools cover typed/text/image/error results, state, progress, delay/cancellation events, catalog changes, oversized output and a side effect followed by connection loss. Tests observe PIDs and append events.

Gateway tests use real MCP clients and those fixtures. Test OneTool's validation, deadline/admission policy, namespaces, redaction, file limits and lifecycle wiring. Upstream behavior gets a fixture contract assertion, not a parallel library test suite. Pure YAML/disk/log rules have focused local tests.

The native `search`, `get_schema`, `execute` input schemas are pinned in `tests/fixtures/code_mode_tools.json`. Re-run the P1 proof before changing the FastMCP minor pin or this fixture. Do not regenerate the expectation to silence a contract failure.

For no-connect status proof, send the raw typed tools/call with public Client.session.send_request. SDK call_tool and call_tool_mcp both validate output schemas with a separate tools/list request after receiving the result. That discovery is a distinct operation.

Documentation Python/JSON examples run against alpha/beta. Config examples are parsed with explicit fixture environment values. Local links are checked without contacting public servers.

Run installed tests in a copied directory outside the checkout, using a fresh environment containing the built wheel. Use paths with spaces. Assert that `onetool.__file__` comes from that environment's site-packages. Run Python 3.12 once to cover the declared floor. Repeat the uv installer proof with no Python on PATH.

The installed cleanup probe checks EOF, SIGINT during blocked work, result-directory removal, owned PIDs and an unrelated process. Publication, main merge, real browser OAuth and the owner's week of daily use are separate owner actions.
