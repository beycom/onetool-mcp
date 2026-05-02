# File vs Mem vs Harness-native Benchmark

Three-way like-for-like comparison: `file` pack vs `mem` pack vs Harness-native tools.
Focus is agent wall-clock cost using identical timing methodology for all three.

---

## Setup

Discover available tools:

```
ot.tools(pattern="mem", info="min")
ot.tools(pattern="file", info="min")
ot.tools(pattern="timer", info="min")
```

Load dev docs into mem (setup only, not timed):

```
mem.write_batch(topic="proj/onetool-mcp/dev", glob_pattern="dev/**/*.md", toc=True, category="context")
mem.list(topic="proj/onetool-mcp/dev/", format="tree", depth=3)
```

---

## Timing Methodology

**All three methods use identical 3-call structure** — this is the only fair comparison:

```
ot_timer.start(name="tN-file")       # call 1
file.xxx(...)                         # call 2
ot_timer.elapsed(name="tN-file", store_as="tN-file")  # call 3

ot_timer.start(name="tN-mem")
mem.xxx(...)
ot_timer.elapsed(name="tN-mem", store_as="tN-mem")

ot_timer.start(name="tN-native")
<Harness-native Read or Grep>
ot_timer.elapsed(name="tN-native", store_as="tN-native")
```

Each elapsed time includes 2 MCP round-trips + the actual tool execution.
This reflects true agent cost, not raw I/O speed.

---

## Test 1: Single File Read

Read `dev/agents/hints.md` (~7KB).

- **file**: `file.read(path="dev/agents/hints.md")`
- **mem**: `mem.read(topic="proj/onetool-mcp/dev/agents/hints.md")`
- **native**: `Read(file_path="<abs_path>/dev/agents/hints.md")`

---

## Test 2: Regex Search Across Docs

Search for `"LogSpan"` with 2 lines of context across all dev docs.

- **file**: `file.grep(pattern="LogSpan", path="dev/", glob="**/*.md", context=2)`
- **mem**: `mem.grep(pattern="LogSpan", topic="proj/onetool-mcp/dev/", context=2)`
- **native**: `Grep(pattern="LogSpan", path="<abs>/dev", glob="**/*.md", output_mode="content", C=2)`

---

## Test 3: Batch Read (8 arch docs)

Read all 8 files under `dev/project/arch/`.

- **file**: `file.read_batch(glob="dev/project/arch/*.md")`
- **mem**: `mem.read_batch(topic="proj/onetool-mcp/dev/project/arch/")`
- **native**: 8x parallel `Read(file_path="...")` calls in one turn

---

## Test 4: Section Extraction (3 sections from 3 docs)

Pre-step (not timed, allowed for all methods): run `file.toc` / `mem.toc` on each file to obtain
section line ranges. All three methods may use pre-known line numbers.

- **file**: `file.slice_batch(items=[{"path": "dev/project/arch/security-model.md", "select": "Layer 2: AST Validation"}, {"path": "dev/project/arch/core-concepts.md", "select": "Packs"}, {"path": "dev/project/arch/request-pipeline.md", "select": "Stages"}])`
- **mem**: `mem.slice_batch(items=[{"topic": "proj/onetool-mcp/dev/project/arch/security-model.md", "select": "Layer 2: AST Validation"}, {"topic": "proj/onetool-mcp/dev/project/arch/core-concepts.md", "select": "Packs"}, {"topic": "proj/onetool-mcp/dev/project/arch/request-pipeline.md", "select": "Stages"}])`
- **native**: 3x parallel `Read(file_path="...", offset=X, limit=Y)` using line ranges from the pre-step toc

Note ergonomic difference: file/mem select by heading name in one call; native requires explicit
line numbers obtained from a separate toc pre-step.

---

## Test 5: Complex Pattern Search

Search for `def \w+(` with 1 line of context across all dev docs.

- **file**: `file.grep(pattern="def \\w+\\(", path="dev/", glob="**/*.md", context=1)`
- **mem**: `mem.grep(pattern="def \\w+\\(", topic="proj/onetool-mcp/dev/", context=1)`
- **native**: `Grep(pattern="def \\w+\\(", path="<abs>/dev", glob="**/*.md", output_mode="content", C=1)`

---

## Collect Results

```
ot_timer.list()
```

---

## Report

Save to `wip/test-output/mem-vs-file-{yyyymmdd}.md`:

| Test | file ms | mem ms | native ms | file winner? | mem winner? | Notes |
|------|---------|--------|-----------|--------------|-------------|-------|
| T1: Single read | | | | | | |
| T2: Regex search | | | | | | |
| T3: Batch read (8) | | | | | | |
| T4: Section extract (3) | | | | | | |
| T5: Pattern search | | | | | | |

Include observations on:
- Where file and mem are closest (smallest gap)
- Where native falls furthest behind
- Any ergonomic differences (e.g. T4: name vs line-number selection)
- Whether file tools are available or skipped (issue not yet implemented)
