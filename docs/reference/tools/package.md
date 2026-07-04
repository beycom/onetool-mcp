# Package

Check latest versions for npm, PyPI packages and search OpenRouter AI models.

Short alias: `pkg`

## Highlights

- Unified version checking across npm and PyPI
- Parallel fetching via ThreadPoolExecutor
- Version comparison support (pass dict with current versions)
- OpenRouter model search with glob patterns

## Functions

| Function | Description |
|----------|-------------|
| `package.audit(path, registry)` | Version-staleness audit for npm or PyPI packages against a manifest file (no CVE/vulnerability lookup) |
| `package.npm(packages)` | Check latest npm package versions |
| `package.pypi(packages)` | Check latest PyPI package versions |
| `package.models(query, provider, limit)` | Search OpenRouter AI models |
| `package.version(registry, packages)` | Unified version check with parallel fetching |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `packages` | list or dict | Package names, or dict mapping names to current versions |
| `path` | str | Project directory to audit for `package.audit()` (default: `"."`) |
| `registry` | str | "npm", "pypi", or "openrouter" |
| `query` | str | Search query for model name/id (case-insensitive) |
| `provider` | str | Filter models by provider (e.g., "anthropic", "openai") |

## Requires

No API key required.

## Configuration

### Required

- No required `tools.package` settings.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.package.timeout` | float | `30.0` | Request timeout in seconds. Range: `1.0-120.0`. |

```yaml
tools:
  package:
    timeout: 30.0
```

### Defaults

- If `tools.package` is omitted, package lookups use the built-in timeout shown above.

## Examples

```python
# Check npm package versions
package.npm(packages=["react", "typescript"])

# Check PyPI package versions
package.pypi(packages=["requests", "httpx"])

# Compare against current versions
package.npm(packages={"react": "18.2.0", "typescript": "5.0.0"})

# Search OpenRouter models
package.models(query="claude-sonnet-4.*", provider="anthropic")

# Unified version check
package.version(registry="npm", packages=["express", "fastify"])
```

## Based on

This tool is based on [mcp-package-version](https://github.com/sammcj/mcp-package-version)
by Sam McLeod, licensed under MIT.
