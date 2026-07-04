#!/usr/bin/env bash
# Demo 2 (required, launch): Codebase -> live whiteboard.
# Explore a codebase with ripgrep/file tools and draw its architecture onto the
# Excalidraw canvas in real time, narrated per subsystem.
# Usage: ./02-codebase-to-whiteboard.sh [PORT]
set -euo pipefail
PORT="${1:-8765}"
run() { onetool direct run --port "$PORT" "$1" --format raw; }
say() { run "narrator.speak(text=$1)"; }

say "'Let us turn a codebase into a live architecture diagram.'"

say "'Opening the whiteboard.'"
run "whiteboard.open()"

say "'First, find the entry points with ripgrep.'"
run "ripgrep.search(pattern='def main', path='src')"
run "ripgrep.count(pattern='import', path='src')"

say "'Read the server module to understand the core.'"
run "file.read(path='src/ot/server.py')"
run "file.grep(pattern='pack', path='src/ot/executor')"

say "'Now draw the architecture: server, executor, packs.'"
run "whiteboard.draw(dsl='Server[MCP Server] -> Executor[Runner]')"
say "'Adding the executor to the pack layer.'"
run "whiteboard.draw(dsl='Executor[Runner] -> Packs[Tool Packs]')"

say "'A codebase, mapped to a diagram, live.'"
run "whiteboard.screenshot()"
