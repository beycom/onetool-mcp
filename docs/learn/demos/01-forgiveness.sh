#!/usr/bin/env bash
# Demo 1 (required, launch): Forgiveness — sloppy calls that all work.
# Usage: ./01-forgiveness.sh [PORT]
set -euo pipefail
PORT="${1:-8765}"
run() { onetool direct run --port "$PORT" "$1" --format raw; }
say() { run "narrator.speak(text=$1)"; }

say "'OneTool forgives sloppy calls. Watch.'"

say "'First: a shortened parameter name. mem dot search, q equals gold price.'"
run "mem.search(q='gold price')"

say "'Second: a pack alias. wb dot draw, instead of the full whiteboard pack name.'"
run "wb.draw(dsl='A[Start] -> B[Forgiven]')"

say "'Third: a proxied tool called camelCase instead of snake_case.'"
run "github.listRepositories()"

say "'Fourth: a typo in a tool name, self-corrected with a did-you-mean suggestion.'"
run "ot.tool_info(name='mem.serach')"

say "'Four sloppy calls. Zero failures.'"
