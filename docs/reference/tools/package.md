# Package

**Latest versions. npm, PyPI, OpenRouter. No API key needed.**

Check latest versions for npm, PyPI packages and search OpenRouter AI models.

| Function | Description |
|----------|-------------|
| `package.npm(packages)` | Check latest npm package versions |
| `package.pypi(packages)` | Check latest PyPI package versions |
| `package.models(query, provider, limit)` | Search OpenRouter AI models |
| `package.version(registry, packages)` | Unified version check with parallel fetching |

**Key Parameters:**
- `packages`: List of package names, or dict mapping names to current versions
- `registry`: "npm", "pypi", or "openrouter"
- `query`: Search query for model name/id (case-insensitive)
- `provider`: Filter models by provider (e.g., "anthropic", "openai")

**No API key required.**

**Based on:** [mcp-package-version](https://github.com/sammcj/mcp-package-version) by Sam McLeod

**Differences from upstream:**
- Unified `version()` function with parallel fetching via ThreadPoolExecutor
- Support for current version comparison (pass dict instead of list)
- OpenRouter model search with glob patterns (e.g., `anthropic/claude-sonnet-4.*`)

**License:** MIT ([LICENSE](../licenses/mcp-package-version-LICENSE))
