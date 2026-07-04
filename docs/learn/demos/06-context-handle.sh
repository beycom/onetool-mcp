#!/usr/bin/env bash
# Demo 6 (optional backlog): The 40KB result that never touched context.
# A big fetch returns a ctx handle instead of inline content; navigate it with
# ctx.toc/ctx.ask, then persist the distilled result with mem.write.
# Usage: ./06-context-handle.sh [PORT]
#
# Prereq: the [util] extra (ctx pack) installed.
set -euo pipefail
PORT="${1:-8765}"
run() { onetool direct run --port "$PORT" "$1" --format raw; }
say() { run "narrator.speak(text=$1)"; }

say "'A forty kilobyte page that never fills your context window.'"

say "'Fetch a large page. Oversized output is stored and returned as a handle.'"
run "__force_context__ = True; webfetch.fetch(url='https://docs.python.org/3/library/asyncio.html')"

say "'Map the stored result with a table of contents — no full read.'"
run "ctx.toc(handle='REPLACE_WITH_HANDLE')"

say "'Ask a question against the stored content directly.'"
run "ctx.ask(handle='REPLACE_WITH_HANDLE', q='What is an event loop?')"

say "'Persist the distilled answer to memory.'"
run "mem.write(topic='asyncio/event-loop', content='Event loop runs and manages async tasks.')"

say "'Forty kilobytes navigated. Zero context spent.'"
