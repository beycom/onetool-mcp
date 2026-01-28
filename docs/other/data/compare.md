# Benchmark Comparison Results


## Scenario: Impact of tool usage - one-shot

With 18 MCP servers loaded, `multiple-mcp` consumes **23x more input tokens** (46,130 vs 1,999) than OneTool for the same task. This translates to **18x higher cost** (2.34¢ vs 0.13¢) and **2x slower** execution (12s vs 6s). The token overhead comes from sending all tool definitions with every request—a cost that scales with the number of configured servers regardless of which tools are actually used.

| Task                  |    in | out | tools | time |  cost | result |
|-----------------------|------:|----:|------:|-----:|------:|--------|
| compare:base          |    33 | 239 |     0 |   5s | 0.07¢ |   FAIL |
| compare:mcp           |  1520 |  98 |     2 |   7s | 0.11¢ |   PASS |
| compare:multiple-mcp  | 46130 | 125 |     2 |  12s | 2.34¢ |   PASS |
| compare:onetool       |  1999 |  95 |     1 |   6s | 0.13¢ |   PASS |
| compare:onetool-proxy |  4654 | 188 |     3 |  11s | 0.29¢ |   PASS |

## Scenario: Impact of tool usage - multi-turn

Multi-turn conversations amplify the token overhead. Over 3 turns, `multi-mcp` accumulates **28x more input tokens** (146,387 vs 5,152) and costs **24x more** (7.35¢ vs 0.30¢). The gap widens because MCP re-sends all tool definitions on every turn, while OneTool maintains a single consolidated interface.

**Developer monthly impact** (20 working days, ~10 conversations/day, ~10 turns each, Claude Opus 4.5 @ $5/M input):
- multi-mcp: ~100M tokens, ~$500/month
- onetool: ~3M tokens, ~$15/month
- **Waste: ~97M tokens/month** (~$485 in pure overhead)

| Task              |     in | out | tools | time |  cost | result |
|-------------------|-------:|----:|------:|-----:|------:|--------|
| compare:multi-mcp | 146387 |  88 |     2 |  17s | 7.35¢ |   PASS |
| compare:onetool   |   5152 | 158 |     2 |  10s | 0.30¢ |   PASS |

## Assumptions
ß
- Benchmark model: google/gemini-3-flash-preview
- multi-mpc has the following MCP servers: package-version, brave-search, context7, github, fetch, sequential-thinking, filesystem, memory, plantuml, excel, ripgrep, gemini-grounding, chunkhound, mcp-alchemy, magic, firecrawl, supabase, railway
