# File vs Mem vs Claude Native Historical Results

**Date:** 2026-02-23
**Method:** 3-call timing (start → tool → elapsed) — measures true agent wall-clock cost including 2 MCP round-trips
**Corpus:** `dev/` directory (33 markdown files, ~135KB total)

---

## Results

| Test | file ms | mem ms | native ms | Winner | Notes |
|------|---------|--------|-----------|--------|-------|
| T1: Single read (hints.md ~7KB) | 4046 | 4282 | 5179 | **file** | file 6% faster than mem; native 28% slower |
| T2: Regex search (LogSpan, C=2) | 5030 | 4099 | 6302 | **mem** | mem 18% faster than file; native 54% slower than mem |
| T3: Batch read (8 arch docs) | 4299 | 4405 | 9191 | **file** | file ≈ mem; native 2.1× slower (8 parallel Reads) |
| T4: Section extract (3 sections) | 4459 | 5524 | 6583 | **file** | file wins; mem 24% slower; native required pre-step toc |
| T5: Pattern search (def \w+\() | 5454 | 4641 | 7487 | **mem** | mem 15% faster than file; native 61% slower than mem |

---

## Raw Timings (ms)

| Test | file | mem | native |
|------|------|-----|--------|
| T1 | 4046 | 4282 | 5179 |
| T2 | 5030 | 4099 | 6302 |
| T3 | 4299 | 4405 | 9191 |
| T4 | 4459 | 5524 | 6583 |
| T5 | 5454 | 4641 | 7487 |
| **Avg** | **4658** | **4590** | **6948** |

---

## Observations

### file vs mem — nearly identical overall

- Average: file=4658ms, mem=4590ms — only **68ms** difference (~1.5%)
- Neither consistently dominates; each wins 2-3 tests depending on workload
- **file wins** on single read (T1) and section extraction (T4)
- **mem wins** on search tasks (T2, T5) and is roughly equal on batch read (T3)
- The file/mem gap is within noise for most tasks — choice should be ergonomic, not performance-based

### Where file and mem are closest

- T3 (batch read): 4299ms vs 4405ms — only 106ms gap (2.5%). Both complete 8-file reads in a single call with identical MCP overhead.
- T1 (single read): 4046ms vs 4282ms — 236ms gap (5.8%). Negligible in practice.

### Where native falls furthest behind

- **T3 (batch read)**: native=9191ms vs file=4299ms — **2.1× slower**. Even with 8 parallel Read calls in one turn, the per-tool overhead accumulates. This is the strongest case for using file/mem over native.
- **T5 (pattern search)**: native=7487ms vs mem=4641ms — **61% slower**. The Grep tool itself is fast but carries the same MCP round-trip overhead.
- **T2 (regex search)**: native=6302ms vs mem=4099ms — **54% slower**.

### Ergonomic differences — T4 is most illustrative

- **file.slice_batch / mem.slice_batch**: Select sections by heading name in a single call. No pre-knowledge of line numbers needed.
- **Native**: Required a separate `file.toc` pre-step to discover line ranges, then 3 parallel Read calls with explicit offsets. More error-prone, requires two agent turns minimum.
- This ergonomic gap (name vs line-number selection) is significant for agents — wrong line numbers produce incorrect extractions silently.

### Native notes

- The native Grep tool is backed by ripgrep and is genuinely fast at the filesystem level, but the MCP round-trip cost (~1.5-2s per call) makes it uncompetitive when multiple calls are needed.
- For single-file targeted reads, native is reasonable but still 15-28% slower than file/mem due to round-trip overhead.
- For batch and search operations, native consistently loses by a large margin.

### mem-specific notes

- All 33 docs were already loaded (duplicates skipped on write_batch). Read operations hit the SQLite cache, which is why mem is competitive with file despite the database overhead.
- mem.grep returns structured, memory-centric output (memory name, match count, slice reference) that is more useful for navigation than raw line output.
- mem.slice_batch accepts heading names (same as file.slice_batch) — no line number lookup needed.

---

## Summary

- **file ≈ mem** — essentially interchangeable on performance (~68ms avg difference)
- **Use file** when working with the live filesystem (files may change, no setup needed)
- **Use mem** when files are pre-loaded and you want search-oriented output or cross-memory grep
- **Avoid native for bulk/search ops** — consistently 40-110% slower due to per-call MCP overhead
- **Native is acceptable** for one-off targeted reads when the exact path and line range are already known
