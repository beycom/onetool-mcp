#!/usr/bin/env bash
# Demo 4 (optional backlog): One tool, 300 fewer schemas.
# Connect, list packs, make a first tool call, then show the token count.
# Usage: ./04-fewer-schemas.sh [PORT]
set -euo pipefail
PORT="${1:-8765}"
run() { onetool direct run --port "$PORT" "$1" --format raw; }
say() { run "narrator.speak(text=$1)"; }

say "'One MCP tool replaces hundreds of tool schemas. Let us prove it.'"

say "'Here are all the packs, behind one tool.'"
run "ot.packs()"

say "'A first real tool call — no schema tax to connect.'"
run "ripgrep.search(pattern='TODO', path='src')"

say "'And the token accounting: a fraction of what many servers would cost.'"
run "ot.stats()"

say "'Unlimited tools. One schema.'"
