# OneTool vs MCPs Historical Performance Comparison

*Measurements captured: February 2026 · [raw data](../results/result-20260223-0334.csv)*

## Scenario: Impact of tool usage - one-shot

With 18 MCP servers loaded, `multiple-mcp` consumes **42x more input tokens** (47,660 vs 1,131) than OneTool for the same task. This translates to **28x higher cost** (2.42¢ vs 0.09¢) and **1.5x slower** execution (7s vs 5s). The token overhead comes from sending all tool definitions with every request — a cost that scales with the number of configured servers regardless of which tools are actually used.

| Task                  | in    | out | tools | time | cost  | result |
| --------------------- | ----: | --: | ----: | ---: | ----: | ------ |
| compare:base          | 34    | 285 | 0     | 4s   | 0.09¢ | FAIL   |
| compare:mcp           | 1516  | 99  | 2     | 6s   | 0.11¢ | PASS   |
| compare:multiple-mcp  | 47660 | 129 | 2     | 7s   | 2.42¢ | PASS   |
| compare:onetool       | 1131  | 95  | 1     | 5s   | 0.09¢ | PASS   |
| compare:onetool-proxy | 1185  | 99  | 1     | 4s   | 0.09¢ | PASS   |

## Scenario: Impact of tool usage - 3-shot

Multi-turn conversations amplify the token overhead. Over 3 turns, `multi-mcp` accumulates **40x more input tokens** (119,258 vs 2,947) and costs **34x more** (5.99¢ vs 0.17¢). The gap widens because MCP re-sends all tool definitions on every turn, while OneTool maintains a single consolidated interface.

**Developer monthly impact** (20 working days, ~10 conversations/day, ~10 turns each, Claude Opus 4.5 @ $5/M input):

- multi-mcp: ~79M tokens, ~$395/month
- onetool: ~2M tokens, ~$10/month
- **Waste: ~77M tokens/month** (~$385 in pure overhead)

| Task              | in     | out | tools | time | cost  | result |
| ----------------- | -----: | --: | ----: | ---: | ----: | ------ |
| compare:multi-mcp | 119258 | 88  | 2     | 13s  | 5.99¢ | PASS   |
| compare:onetool   | 2947   | 90  | 2     | 10s  | 0.17¢ | PASS   |

## Assumptions

- Benchmark model: google/gemini-3-flash-preview
- multi-mcp has the following MCP servers: package-version, brave-search, context7, github, fetch, sequential-thinking, filesystem, memory, plantuml, excel, ripgrep, gemini-grounding, mcp-alchemy, magic, supabase, railway
