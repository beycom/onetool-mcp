# Package

**Latest versions. npm, PyPI, OpenRouter. No API key needed.**

Check latest versions for npm, PyPI packages and search OpenRouter AI models.

## Highlights

- Unified version checking across npm and PyPI
- Parallel fetching via ThreadPoolExecutor
- Version comparison support (pass dict with current versions)
- OpenRouter model search with glob patterns

## Functions

| Function | Description |
|----------|-------------|
| `package.npm(packages)` | Check latest npm package versions |
| `package.pypi(packages)` | Check latest PyPI package versions |
| `package.models(query, provider, limit)` | Search OpenRouter AI models |
| `package.version(registry, packages)` | Unified version check with parallel fetching |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `packages` | list or dict | Package names, or dict mapping names to current versions |
| `registry` | str | "npm", "pypi", or "openrouter" |
| `query` | str | Search query for model name/id (case-insensitive) |
| `provider` | str | Filter models by provider (e.g., "anthropic", "openai") |

## Requires

No API key required.

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

## Source

[npm Registry API](https://github.com/npm/registry) | [PyPI JSON API](https://warehouse.pypa.io/api-reference/json.html) | [OpenRouter API](https://openrouter.ai/docs)

## Based on

[mcp-package-version](https://github.com/sammcj/mcp-package-version) by Sam McLeod (MIT)
