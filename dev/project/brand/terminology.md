# Terminology Style Guide

Consistent terminology for OneTool documentation.

---

## Agent vs LLM

Use **"agent"** consistently when referring to tool-using behavior. Avoid "LLM", "AI", "model", "Claude", "the AI".

### When to Use "Agent"

| Context | Term | Example |
|---------|------|---------|
| First mention in a doc | "AI agent" or "the agent (Claude, GPT, etc.)" | "OneTool changes how AI agents use tools." |
| Subsequent mentions | "agent" | "The agent generates code you can review." |
| Headings/taglines | "agent" | "Agent + MCP testing" |
| Technical comparisons | "agent" | "Agent tool selection errors" |

### Exceptions (Keep These Terms)

| Term | When to use |
|------|-------------|
| **LLM** | Model characteristics: "LLM performance degrades with context length" |
| **LLM-powered** | Describing the engine: "LLM-powered transformation" |
| **`llm.transform`** | Pack/function names (product names) |
| **model** | Configuration: "transform.model", "Gemini model" |
| **Claude Code** | Product name in setup instructions |

### Examples

**Correct:**

- "The agent generates code you can review before execution"
- "Explicit calls prevent agent tool selection errors"
- "LLM performance degrades as tokens increase" (model characteristic)

**Avoid:**

- ~~"The LLM generates code"~~ → "The agent generates code"
- ~~"Guide the LLM"~~ → "Guide the agent"
- ~~"LLM tool selection"~~ → "Agent tool selection"

---

## MCP Terminology

Use Anthropic's standard MCP terminology consistently.

| Term | Use for | Not |
|------|---------|-----|
| **MCP server** | A connected tool provider | "MCP tool", "MCP service" |
| **tool definitions** | The JSON schemas sent to agent | "tool schemas", "tool specs" |
| **tool calls** | Individual invocations | "tool requests", "API calls" |
| **tool use** | The practice of using tools | "tool calling" (as a noun) |
| **context window** | The token space | "context", "context budget" |
| **context rot** | Performance degradation from tokens | (OneTool-specific term) |

### Examples

- "MCP servers consume tokens through tool definitions"
- "Each tool call requires inference"
- "Tool use accuracy improved to 88%"
- "Context window is limited"

---

## OneTool-Specific Terms

| Term | Definition |
|------|------------|
| **tool tax** | Per-request token cost of tool definitions resent by every MCP server |
| **context rot** | Performance degradation as context window fills with tool definitions |
| **context economy** | Keeping tool outputs (not just definitions) out of the context window — `ctx` handles, `img` delegation, `file.slice` |
| **pack** | A collection of related tools (e.g., `brave`, `file`, `db`) |
| **explicit calls** | Direct tool invocation via code instead of agent selection |
| **snippet** | Reusable code template with Jinja2 substitution |
| **alias** | Short name for a pack (`wb`, `ctx`, `img`) or tool function |
| **handle** | Stable reference to a stored large output (`ctx_…`) or loaded image (`#…`) |
| **`__onetool`** | Canonical explicit trigger (short form `__ot`); `__run`/`__r` removed in v3 |
| **direct API / direct CLI** | Authenticated HTTP/shell access to a running OneTool process, bypassing MCP |

---

## Capitalization

| Term | Capitalization |
|------|----------------|
| OneTool | Capital O, capital T |
| MCP | All caps |
| Claude Code | Title case (product name) |
| pack names | Lowercase (`brave`, `file`) |
| tool names | Lowercase (`brave.search`) |
