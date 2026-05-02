# Build a Wikipedia Tool

Build a "wiki" tool pack with 3 tools: page, summary, data.

Start with `ot.help()` then `ot.tools(pattern="ot_forge", info="min")`.

Steps:
1. Check tools_dir is configured: `ot.config()`
2. Scaffold: `ot_forge.create_ext(name="wiki")`
3. Implement:
   - `page(slug, size=10)` — fetch https://en.wikipedia.org/wiki/{slug}, truncate to size KB
   - `summary(slug, prompt)` — use `call_tool("llm.transform", ...)` to summarize page content
   - `data(slug)` — fetch JSON from https://en.wikipedia.org/api/rest_v1/page/summary/{slug}
   - Use httpx.Client for HTTP, LogSpan for logging, return error strings on failure
4. Validate: `ot_forge.validate_ext(path=...)`
5. Reload: `ot.reload()`
6. Test all 3 tools with slugs: Anthropic, OpenAI, Moonshot_AI
