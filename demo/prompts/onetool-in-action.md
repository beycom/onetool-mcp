# OneTool in Action


## Compare the Search

```
Title: Compare the Search
Explain each step so it is easy to follow what you did and why. Use 🧿 to highlight these explanations.

Use onetool ot.help() with info="full" to understand how best to use onetool tools. 
I want to compare onetool tools and snippets to Claude Code's built-in search.
Optimise calls to get the best results. Tweak onetool tool parameters for better output: increase count, adjust return format, include links, etc.

Test both tools and relevant snippets to answer the questions below.
Compare and score them (out of 10) based on quality and speed.

Columns:
Tool | Output | Speed | Quality | Overall | Recommended For | Call / Snippet 
Call / Snippet  should have all relevant parameters, but the queries should be "..."

Run searches sequentially so timing is not impacted and measure timing.
DO NOT actually provide the answer for the question.

Tools and snippets to use:
- OneTool Tools: brave.search, firecrawl.search, ground.docs, ground.search, context7
- OneTool Snippets: $brv, $brv_research, $c7, $f, $f_fetch, $g, $g_reddit, $web_data, $web_summary
- Claude: WebSearch

Questions:
- MCP resources vs tools?
- When to use MCP resources?
- When to use MCP tools?

Once done, provide a list of all tool calls and snippets used:
- Claude
    - ...
- OneTool
  - Introspection
    - ...
  - Tools
    - ...
  - Snippets
    - ...
```

## Build a Wikipedia Tool

```
Title: Build a Wikipedia Tool
Explain each step so it is easy to follow what you did and why. Use 🧿 to highlight these explanations.

- Learn onetool with `ot.help(info="full")` and `scaffold.templates()`
- Verify tools_dir is configured for ~/.onetool/tools using `ot.config()`. If not, add `~/.onetool/tools/**/*.py` to the config.
- Scaffold a "wiki" pack using `scaffold.create(name="wiki", scope="global", template="simple")`

- Implement these tools:
  - `page(slug, size=10)` - Fetch HTML from https://en.wikipedia.org/wiki/{slug}, truncate to size KB
  - `summary(slug, prompt)` - Use call_tool("llm.transform", ...) to summarize page content  
  - `data(slug)` - Fetch JSON from https://en.wikipedia.org/api/rest_v1/page/summary/{slug}

- Implementation notes:
  - Use `from ot.logging import LogSpan` for structured logging
  - Use `from ot.tools import call_tool` for llm.transform only
  - Use httpx.Client for HTTP requests (bundled, no deps needed)
  - Return error strings/dicts on failure (no raise)

- Validate with `scaffold.validate(path=...)` and show the output as markdown

- Reload with `ot.reload()` before testing the new tool

- Test all three tools with slugs: Anthropic, OpenAI, Moonshot_AI

Finally, list all onetool commands used.
```
